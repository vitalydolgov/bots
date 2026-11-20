import os
import re
import subprocess
import sys
from pathlib import Path

from google.adk.agents import LlmAgent
from google.adk.apps.app import App, EventsCompactionConfig
from google.adk.environment import LocalEnvironment
from google.adk.models.lite_llm import LiteLlm
from google.adk.skills import load_skill_from_dir
from google.adk.tools.environment import EnvironmentToolset
from google.adk.tools.skill_toolset import SkillToolset

from config import BOT_ROOT, WORKSPACE_DIR, bot_dir, load_config
from mcp_images import mcp_image_callback
from mcp_servers import load_mcps
from modalities import detect_input_modalities
from roster import roster_instructions
from skills import SKILLS_DIR, seed_skills
from tools.date import DATE_TOOLS
from tools.memory import make_memory_tools, memory_instructions
from tools.read_image import READ_IMAGE_TOOLS

PROMPTS_DIR = Path(__file__).resolve().parent / "instructions" / "prompts"
MODALITY_PROMPTS = {"image": PROMPTS_DIR / "vision.md"}
CHROME_SCRIPT = Path(__file__).resolve().parent / "scripts" / "start-chrome.sh"

_bootstrap_done = False


def _bootstrap() -> None:
    global _bootstrap_done
    if _bootstrap_done:
        return
    _bootstrap_done = True
    seed_skills()
    subprocess.run(["bash", str(CHROME_SCRIPT), str(WORKSPACE_DIR)], check=False, timeout=75)


def date_instructions() -> str:
    return (PROMPTS_DIR / "date.md").read_text(encoding="utf-8").strip()


def identity_instructions(identifier: str, identity_path: Path) -> str:
    built_in = (PROMPTS_DIR / "identity.md").read_text(encoding="utf-8").strip().format(identifier=identifier)
    try:
        user_identity = identity_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return built_in
    if not user_identity:
        return built_in
    return f"{built_in}\n\n{user_identity}"


def modality_instructions(modalities: list[str]) -> str:
    parts = []
    for modality in modalities:
        path = MODALITY_PROMPTS.get(modality)
        if path is not None:
            parts.append(path.read_text(encoding="utf-8").strip())
    return "\n\n".join(parts)


def _adk_name(raw: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9_-]", "-", raw)
    if not name or not name[0].isalpha():
        name = f"bot-{name}"
    return name


def create_app(profile: str | None = None) -> App:
    _bootstrap()
    config = load_config(profile)
    profile_dir = bot_dir(profile)
    bot_name = profile or "bot"
    agent_name = _adk_name(bot_name)
    identity_path = (profile_dir or BOT_ROOT) / "IDENTITY.md"

    modalities = config.input_modalities or detect_input_modalities(config.base_url, config.model, config.api_key_env_var)
    instructions = "\n\n".join(part for part in (identity_instructions(bot_name, identity_path), modality_instructions(modalities), date_instructions(), roster_instructions(), memory_instructions()) if part)

    api_key = os.environ.get(config.api_key_env_var, "").strip()
    if not api_key:
        raise RuntimeError(
            f"Environment variable {config.api_key_env_var} is not set; "
            "the agent cannot reach the model endpoint without it."
        )

    model = LiteLlm(
        model=f"openai/{config.model}",
        api_base=config.base_url,
        api_key=api_key,
    )

    environment_toolset = EnvironmentToolset(environment=LocalEnvironment(working_dir=WORKSPACE_DIR))

    skills = []
    if SKILLS_DIR.is_dir():
        for skill_dir in sorted(SKILLS_DIR.iterdir()):
            if not (skill_dir / "SKILL.md").is_file():
                continue
            try:
                skills.append(load_skill_from_dir(skill_dir))
            except Exception as error:
                print(f"warning: skipping skill {skill_dir.name}: {error}", file=sys.stderr)

    tools = [*make_memory_tools(profile), *READ_IMAGE_TOOLS, *DATE_TOOLS, environment_toolset]
    if skills:
        tools.append(SkillToolset(skills=skills))
    tools.extend(load_mcps(profile))

    agent = LlmAgent(
        name=agent_name,
        model=model,
        instruction=instructions,
        tools=tools,
        after_tool_callback=mcp_image_callback,
    )

    return App(
        name=agent_name,
        root_agent=agent,
        events_compaction_config=EventsCompactionConfig(
            token_threshold=config.context_window,
            event_retention_size=10,
        ),
    )
