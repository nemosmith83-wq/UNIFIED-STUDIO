"""Production workflow contracts for Unified Studio creative workbench."""
from typing import Any, Dict, List
WORKFLOWS: Dict[str, Dict[str, Any]] = {
 "content":{"label":"Content Studio","goal":"Produce complete written campaign content.","deliverables":["campaign_copy","brand_story","script","social_pack"],"stages":["Brief","Strategy","Draft","Editorial pass","Final deliverable"],"visual":False},
 "image":{"label":"Image Studio","goal":"Create image concepts and production prompts.","deliverables":["hero_image","image_set","portrait","product_visual"],"stages":["Brief","Art direction","Prompt design","Image generation","QA"],"visual":True},
 "video":{"label":"Video Studio","goal":"Create video treatment, script, shot plan, prompts.","deliverables":["commercial","social_video","trailer","storyboard"],"stages":["Brief","Concept","Script","Shot list","Production prompts","Review"],"visual":True},
 "audio":{"label":"Audio Studio","goal":"Create audio concept, script, and sound direction.","deliverables":["voiceover","music_brief","sound_design","audio_ad"],"stages":["Brief","Concept","Script","Sound direction","Mix notes","Review"],"visual":False},
 "comic":{"label":"Comic Forge","goal":"Turn story into sequential comic panels.","deliverables":["comic_page","comic_sequence","graphic_narrative"],"stages":["Story","Page structure","Continuity","Panel prompts","Generation","QA"],"visual":True},
 "poster":{"label":"Poster & Key Visual","goal":"Create campaign key visual, layout and typography direction.","deliverables":["campaign_poster","key_visual","event_poster"],"stages":["Objective","Concept","Composition","Copy hierarchy","Generation","QA"],"visual":True},
 "environment":{"label":"Environment Studio","goal":"Design locations with coherent viewpoints.","deliverables":["environment_design","interior","exterior","location_concept"],"stages":["Location brief","Spatial concept","Materials and lighting","Viewpoints","Generation","Review"],"visual":True},
 "talent":{"label":"Talent & Model Studio","goal":"Create casting direction and consistent character looks.","deliverables":["talent_look","character_sheet","campaign_model"],"stages":["Role","Talent direction","Wardrobe","Look prompts","Generation","Review"],"visual":True},
}
def get_workflows() -> List[Dict[str, Any]]:
 return [{"id":k,"label":v["label"],"goal":v["goal"],"deliverables":list(v["deliverables"]),"stages":list(v["stages"]),"visual":bool(v["visual"])} for k,v in WORKFLOWS.items()]
def build_production_messages(studio: str, deliverable: str, brief: str, asset_count: int) -> List[Dict[str,str]]:
 if studio not in WORKFLOWS: raise ValueError("Unknown studio")
 workflow=WORKFLOWS[studio]
 if deliverable not in workflow["deliverables"]: raise ValueError("Unsupported deliverable")
 count=max(1,min(int(asset_count),4))
 visual=workflow["visual"]
 system=("You are Unified Studio production lead. Use only user brief; do not invent brand/product facts. "
 "List missing facts. Return one JSON object with title, creative_direction, deliverable_text, missing_information, production_stages, image_prompts, quality_checklist. "
 "Stages are objects with stage and completion_criteria. Complete deliverable, not a summary. "
 "Preserve any supplied person's identity, face, hair and natural proportions exactly. "
 "Visual prompts include FUJIFILM GFX100RF and a small handwritten FadeL signature at bottom-left unless user says otherwise. "
 "Never claim generated media unless a tool returned it.")
 user=("STUDIO: "+workflow["label"]+" ("+studio+")\nGOAL: "+workflow["goal"]+"\nDELIVERABLE: "+deliverable+
 "\nASSET COUNT: "+str(count if visual else 0)+"\nSTAGES: "+str(workflow["stages"])+
 "\nUSER BRIEF:\n"+brief.strip()+"\nReturn JSON. image_prompts must contain exactly "+str(count if visual else 0)+
 " complete prompts. For comic, use sequential distinct panels with continuity; for environment/talent, distinct views/looks with consistent design.")
 return [{"role":"system","content":system},{"role":"user","content":user}]
def parse_production_json(raw: str) -> Dict[str,Any]:
 import json
 text=(raw or "").strip()
 fence=chr(96)*3
 if text.startswith(fence): text=text.split("\n",1)[-1]
 if text.endswith(fence): text=text[:-3]
 start,end=text.find("{"),text.rfind("}")
 if start<0 or end<start: raise ValueError("No JSON production package returned")
 data=json.loads(text[start:end+1])
 if not isinstance(data,dict): raise ValueError("Production package must be an object")
 return data
def validate_production_package(data: Dict[str,Any], studio: str, asset_count: int) -> List[str]:
 blockers=[]
 for key in ("title","creative_direction","deliverable_text"):
  if not isinstance(data.get(key),str) or not data[key].strip(): blockers.append("Missing required field: "+key)
 stages=data.get("production_stages")
 if not isinstance(stages,list) or not stages: blockers.append("Production stages missing")
 elif any(not isinstance(x,dict) or not x.get("stage") or not x.get("completion_criteria") for x in stages): blockers.append("Stage needs name and completion criteria")
 prompts=data.get("image_prompts",[])
 if not isinstance(prompts,list): blockers.append("image_prompts must be a list")
 else:
  expected=max(0,min(int(asset_count),4)) if WORKFLOWS.get(studio,{}).get("visual") else 0
  valid=[x for x in prompts if isinstance(x,str) and x.strip()]
  if len(valid)!=expected: blockers.append("Expected "+str(expected)+" complete image prompts; received "+str(len(valid)))
 return blockers
