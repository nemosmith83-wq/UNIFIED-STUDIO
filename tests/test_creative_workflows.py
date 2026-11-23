import unittest
from backend.creative_workflows import WORKFLOWS, build_production_messages, get_workflows, parse_production_json, validate_production_package

class CreativeWorkflowTests(unittest.TestCase):
    def test_eight_workflows_are_available(self):
        self.assertEqual(len(get_workflows()), 8)
        self.assertEqual(set(WORKFLOWS), {item["id"] for item in get_workflows()})
    def test_visual_prompt_contract_includes_camera_and_signature(self):
        messages = build_production_messages("image", "image_set", "Create campaign image", 3)
        self.assertIn("FUJIFILM GFX100RF", messages[0]["content"])
        self.assertIn("FadeL", messages[0]["content"])
        self.assertIn("exactly 3", messages[1]["content"])
    def test_nonvisual_requires_no_image_prompts(self):
        messages = build_production_messages("content", "campaign_copy", "Write campaign copy", 4)
        self.assertIn("ASSET COUNT: 0", messages[1]["content"])
        data = {"title":"Campaign","creative_direction":"Direct","deliverable_text":"Complete copy","production_stages":[{"stage":"Draft","completion_criteria":"Copy complete"}],"image_prompts":[]}
        self.assertEqual(validate_production_package(data, "content", 4), [])
    def test_invalid_studio_or_deliverable_is_rejected(self):
        with self.assertRaises(ValueError): build_production_messages("unknown", "x", "brief", 1)
        with self.assertRaises(ValueError): build_production_messages("image", "unsupported", "brief", 1)
    def test_json_fence_and_prompt_count_qa(self):
        raw = chr(96)*3 + "json\n" + '{"title":"Set","creative_direction":"Direction","deliverable_text":"Treatment","production_stages":[{"stage":"Create","completion_criteria":"Ready"}],"image_prompts":["one"]}' + "\n" + chr(96)*3
        data = parse_production_json(raw)
        self.assertTrue(any("Expected 2" in x for x in validate_production_package(data, "image", 2)))

if __name__ == "__main__":
    unittest.main()
