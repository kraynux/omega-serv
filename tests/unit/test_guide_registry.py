"""Coherence du guide d'aide (OMEGA-SERV_PLAN-DETAILLE_GUIDE_AIDE.md §6) :
chaque fiche ecrite doit reference un ecran reellement present dans
l'arborescence de navigation (menu_tree.py), et chaque fiche/FAQ doit
avoir un contenu complet - jamais une fiche vide ou orpheline."""
import unittest

from omega_serv.interfaces.tui.guide.menu_tree import GUIDE_MENU_ENTRIES
from omega_serv.interfaces.tui.guide.registry import ALL_FAQ_ENTRIES, SCREEN_GUIDES


class TestGuideRegistryCoherence(unittest.TestCase):
    def test_every_documented_screen_is_in_the_menu_tree(self):
        menu_screen_names = {entry.screen_class_name for entry in GUIDE_MENU_ENTRIES}
        orphans = set(SCREEN_GUIDES) - menu_screen_names
        self.assertEqual(orphans, set(), f"Fiches sans entree dans menu_tree.py : {orphans}")

    def test_menu_tree_has_no_duplicate_screen_names(self):
        names = [entry.screen_class_name for entry in GUIDE_MENU_ENTRIES]
        self.assertEqual(len(names), len(set(names)), "Doublon dans menu_tree.py")

    def test_registry_key_matches_the_guide_own_screen_class_name(self):
        for key, guide in SCREEN_GUIDES.items():
            self.assertEqual(key, guide.screen_class_name)

    def test_every_screen_guide_has_non_empty_core_content(self):
        for guide in SCREEN_GUIDES.values():
            self.assertTrue(guide.title.strip(), guide.screen_class_name)
            self.assertTrue(guide.acces.strip(), guide.screen_class_name)
            self.assertTrue(guide.definition.strip(), guide.screen_class_name)

    def test_every_field_guide_has_all_four_dimensions(self):
        for guide in SCREEN_GUIDES.values():
            for guide_field in guide.fields:
                for dimension in (
                    guide_field.label, guide_field.definition,
                    guide_field.utilisation, guide_field.action, guide_field.reaction,
                ):
                    self.assertTrue(dimension.strip(), f"{guide.screen_class_name}/{guide_field.label}")


class TestFaqCoherence(unittest.TestCase):
    def test_every_faq_entry_has_non_empty_content(self):
        for entry in ALL_FAQ_ENTRIES:
            self.assertTrue(entry.category.strip())
            self.assertTrue(entry.question.strip())
            self.assertTrue(entry.answer.strip())


if __name__ == "__main__":
    unittest.main()
