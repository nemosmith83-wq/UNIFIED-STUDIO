"""Production workflow contracts for Unified Studio creative workbench."""
from typing import Any, Dict, List

WORKFLOWS: Dict[str, Dict[str, Any]] = {
    "content": {
        "label": "Content Studio",
        "goal": "Produce complete written campaign content.",
        "deliverables": ["campaign_copy", "brand_story", "script", "social_pack"],
        "stages": ["Brief", "Strategy", "Draft", "Editorial pass", "Final deliverable"],
        "visual": False,
    },
    "image": {
        "label": "Image Studio",
        "goal": "Create image concepts and production prompts.",
        "deliverables": ["hero_image", "image_set", "portrait", "product_visual"],
        "stages": ["Brief", "Art direction", "Prompt design", "Image generation", "QA"],
        "visual": True,
    },
    "video": {
        "label": "Video Studio",
        "goal": "Create video treatment, script, shot plan, prompts.",
        "deliverables": ["commercial", "social_video", "trailer", "storyboard"],
        "stages": ["Brief", "Concept", "Script", "Shot list", "Production prompts", "Review"],
        "visual": True,
    },
    "audio": {
        "label": "Audio Studio",
        "goal": "Create audio concept, script, and sound direction.",
        "deliverables": ["voiceover", "music_brief", "sound_design", "audio_ad"],
        "stages": ["Brief", "Concept", "Script", "Sound direction", "Mix notes", "Review"],
        "visual": False,
    },
    "comic": {
        "label": "Comic Forge",
        "goal": "Turn story into sequential comic panels.",
        "deliverables": ["comic_page", "comic_sequence", "graphic_narrative"],
        "stages": ["Story", "Page structure", "Continuity", "Panel prompts", "Generation", "QA"],
        "visual": True,
    },
    "poster": {
        "label": "Poster & Key Visual",
        "goal": "Create campaign key visual, layout and typography direction.",
        "deliverables": ["campaign_poster", "key_visual", "event_poster"],
        "stages": ["Objective", "Concept", "Composition", "Copy hierarchy", "Generation", "QA"],
        "visual": True,
    },
    "environment": {
        "label": "Environment Studio",
        "goal": "Design locations with coherent viewpoints.",
        "deliverables": ["environment_design", "interior", "exterior", "location_concept"],
        "stages": ["Location brief", "Spatial concept", "Materials and lighting", "Viewpoints", "Generation", "Review"],
        "visual": True,
    },
    "talent": {
        "label": "Talent & Model Studio",
        "goal": "Create casting direction and consistent character looks.",
        "deliverables": ["talent_look", "character_sheet", "campaign_model"],
        "stages": ["Role", "Talent direction", "Wardrobe", "Look prompts", "Generation", "Review"],
        "visual": True,
    },
}


def get_workflows() -> List[Dict[str, Any]]:
    return [
        {
            "id": key,
            "label": value["label"],
            "goal": value["goal"],
            "deliverables": list(value["deliverables"]),
            "stages": list(value["stages"]),
            "visual": bool(value["visual"]),
        }
        for key, value in WORKFLOWS.items()
    ]


def build_production_messages(
    studio: str, deliverable: str, brief: str, asset_count: int
) -> List[Dict[str, str]]:
    if studio not in WORKFLOWS:
        raise ValueError("Unknown studio")
    workflow = WORKFLOWS[studio]
    if deliverable not in workflow["deliverables"]:
        raise ValueError("Unsupported deliverable")

    count = max(1, min(int(asset_count), 4))
    visual = workflow["visual"]
    expected_prompts = count if visual else 0
    system = (
        "You are Unified Studio production lead. Use only user brief; do not invent brand/product facts. "
        "List missing facts. Return one JSON object with title, creative_direction, deliverable_text, "
        "missing_information, production_stages, image_prompts, quality_checklist. "
        "Stages are objects with stage and completion_criteria. Complete deliverable, not a summary. "
        "Preserve any supplied person's identity, face, hair and natural proportions exactly. "
        "Visual prompts include FUJIFILM GFX100RF and a small handwritten FadeL signature at bottom-left "
        "unless user says otherwise. Never claim generated media unless a tool returned it."
    )
    user = (
        "STUDIO: " + workflow["label"] + " (" + studio + ")\n"
        "GOAL: " + workflow["goal"] + "\n"
        "DELIVERABLE: " + deliverable + "\n"
        "ASSET COUNT: " + str(expected_prompts) + "\n"
        "STAGES: " + str(workflow["stages"]) + "\n"
        "USER BRIEF:\n" + brief.strip() + "\n"
        "Return JSON. image_prompts must contain exactly " + str(expected_prompts)
        + " complete prompts. For comic, use sequential distinct panels with continuity; "
        "for environment/talent, distinct views/looks with consistent design."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_production_json(raw: str) -> Dict[str, Any]:
    import json

    text = (raw or "").strip()
    fence = chr(96) * 3
    if text.startswith(fence):
        text = text.split("\n", 1)[-1]
    if text.endswith(fence):
        text = text[:-3]
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("No JSON production package returned")
    data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("Production package must be an object")
    return data


def validate_production_package(
    data: Dict[str, Any], studio: str, asset_count: int
) -> List[str]:
    blockers: List[str] = []

    for key in ("title", "creative_direction", "deliverable_text"):
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            blockers.append("Missing required field: " + key)

    missing = data.get("missing_information")
    if not isinstance(missing, list):
        blockers.append("missing_information must be a list")
    elif any(not isinstance(item, str) or not item.strip() for item in missing):
        blockers.append("missing_information items must be non-empty strings")

    checklist = data.get("quality_checklist")
    if not isinstance(checklist, list) or not checklist:
        blockers.append("quality_checklist must be a non-empty list")
    elif any(not isinstance(item, str) or not item.strip() for item in checklist):
        blockers.append("quality_checklist items must be non-empty strings")

    stages = data.get("production_stages")
    if not isinstance(stages, list) or not stages:
        blockers.append("Production stages missing")
    elif any(
        not isinstance(item, dict)
        or not isinstance(item.get("stage"), str)
        or not item["stage"].strip()
        or not isinstance(item.get("completion_criteria"), str)
        or not item["completion_criteria"].strip()
        for item in stages
    ):
        blockers.append("Stage needs name and completion criteria")

    prompts = data.get("image_prompts")
    if not isinstance(prompts, list):
        blockers.append("image_prompts must be a list")
    else:
        expected = (
            max(0, min(int(asset_count), 4))
            if WORKFLOWS.get(studio, {}).get("visual")
            else 0
        )
        valid_prompts = [
            item for item in prompts if isinstance(item, str) and item.strip()
        ]
        if len(prompts) != expected or len(valid_prompts) != expected:
            blockers.append(
                "Expected "
                + str(expected)
                + " complete image prompts; received "
                + str(len(valid_prompts))
            )

    return blockers
