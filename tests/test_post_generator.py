import unittest

from src.post_generator import OllamaError, build_prompt, format_post, parse_post_response


class PostGeneratorTest(unittest.TestCase):
    def test_prompt_includes_source_and_json_contract(self) -> None:
        prompt = build_prompt("Válvula de bola 3 vías", "English")

        self.assertIn("Válvula de bola 3 vías", prompt)
        self.assertIn('"characteristics"', prompt)
        self.assertIn("exactly three", prompt)

    def test_parse_and_format_post(self) -> None:
        draft = parse_post_response(
            '{"product_name":"157S-M Float Type Combo",'
            '"characteristics":["For boilers of any steaming capacity",'
            '"Monel bellows for corrosion resistance", "Manual reset & max pressure 150 PSI"],'
            '"call_to_action":"Contact us for more information!"}'
        )

        self.assertEqual(draft.product_name, "157S-M Float Type Combo")
        self.assertEqual(len(draft.characteristics), 3)
        self.assertEqual(
            format_post(draft),
            "157S-M Float Type Combo\n"
            "- For boilers of any steaming capacity\n"
            "- Monel bellows for corrosion resistance\n"
            "- Manual reset & max pressure 150 PSI\n\n"
            "Contact us for more information!",
        )

    def test_parse_requires_three_characteristics(self) -> None:
        with self.assertRaises(OllamaError):
            parse_post_response(
                '{"product_name":"Product","characteristics":["Only one"],'
                '"call_to_action":"Contact us"}'
            )

        with self.assertRaises(OllamaError):
            parse_post_response(
                '{"product_name":"Product","characteristics":["One", "Two", "Three", "Four"],'
                '"call_to_action":"Contact us"}'
            )

    def test_parse_requires_json_object(self) -> None:
        with self.assertRaises(OllamaError):
            parse_post_response('["not", "a", "post"]')


if __name__ == "__main__":
    unittest.main()
