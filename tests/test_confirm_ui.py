"""Confirmations and the delete-character button (static checks over public/index.html and public/admin.js).

Deleting or changing a password always goes through one in-panel confirmation modal (no native confirm()),
and a character is deleted by typing its exact name, which the server also requires.
"""

import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def function_body(js, name):
    """Source of `function name(...) { ... }` found by brace matching."""
    start = js.index("function %s(" % name)
    depth = 0
    for i in range(js.index("{", start), len(js)):
        if js[i] == "{":
            depth += 1
        elif js[i] == "}":
            depth -= 1
            if depth == 0:
                return js[start:i + 1]
    raise AssertionError("unbalanced braces in " + name)


class ConfirmModalMarkupTest(unittest.TestCase):
    def setUp(self):
        self.html = read("public", "index.html")
        match = re.search(r'<div id="modal-confirm".*?\n  </div>\n', self.html, re.S)
        self.assertIsNotNone(match, "modal-confirm is missing")
        self.modal = match.group(0)

    def test_it_is_a_hidden_labelled_alert_dialog(self):
        self.assertRegex(self.modal, r'<div id="modal-confirm" class="modal-backdrop" role="alertdialog" aria-modal="true"')
        self.assertIn('aria-labelledby="confirm-modal-title"', self.modal)
        self.assertIn('aria-describedby="confirm-message"', self.modal)
        self.assertRegex(self.modal.split(">")[0] + ">", r"\bhidden\b")

    def test_it_has_a_title_a_message_and_a_form_with_cancel_and_confirm(self):
        for needle in ('id="confirm-modal-title"', 'id="confirm-message"', 'id="form-confirm"', 'id="confirm-submit"',
                       'id="confirm-cancel"', 'data-close-modal'):
            self.assertIn(needle, self.modal)
        self.assertRegex(self.modal, r'<button type="submit" id="confirm-submit"')

    def test_the_typed_confirmation_field_is_hidden_until_asked_for_and_labelled(self):
        self.assertRegex(self.modal, r'<div id="confirm-typed-group" class="form-group" hidden>')
        self.assertRegex(self.modal, r'<label class="form-label" id="confirm-typed-label" for="confirm-typed-input"')
        self.assertRegex(self.modal, r'<input type="text" id="confirm-typed-input"[^>]*autocomplete="off"')

    def test_it_loads_after_the_other_modals_so_it_stacks_above_them(self):
        self.assertGreater(self.html.index('id="modal-confirm"'), self.html.index('id="modal-password"'))
        self.assertGreater(self.html.index('id="modal-confirm"'), self.html.index('id="modal-delete"'))


class ConfirmBehaviourTest(unittest.TestCase):
    def setUp(self):
        self.js = read("public", "admin.js")

    def test_cancel_close_and_escape_all_answer_no(self):
        self.assertRegex(function_body(self.js, "closeModal"), r"modalEl === els\.modalConfirm\) settleConfirm\(false\)")

    def test_the_typed_name_must_match_exactly_before_confirm_is_enabled_and_again_on_submit(self):
        ask = function_body(self.js, "askConfirm")
        self.assertIn("confirmSubmit.disabled = typed", ask)
        self.assertRegex(self.js, r"[!=]== confirmState\.expected")
        self.assertNotRegex(self.js, r"confirmTypedInput\.value\.trim\(\)")
        self.assertIn("settleConfirm(true)", function_body(self.js, "handleConfirmSubmit"))

    def test_the_question_text_is_set_as_text_never_as_html(self):
        ask = function_body(self.js, "askConfirm")
        self.assertIn("confirmMessage.textContent", ask)
        self.assertNotIn("confirmMessage.innerHTML", ask)
        self.assertIn("confirmTitle.textContent", ask)

    def test_a_new_question_cancels_the_pending_one(self):
        self.assertRegex(function_body(self.js, "askConfirm"), r"^function askConfirm\([^)]*\) \{\s*settleConfirm\(false\);")

    def test_a_safe_default_gets_the_focus(self):
        ask = function_body(self.js, "askConfirm")
        self.assertIn("confirmTypedInput.focus()", ask)
        self.assertIn("confirmCancel.focus()", ask)


class ActionsAskFirstTest(unittest.TestCase):
    def setUp(self):
        self.js = read("public", "admin.js")

    def test_changing_a_password_asks_before_sending(self):
        body = function_body(self.js, "handleUpdatePassword")
        self.assertIn("askConfirm(", body)
        self.assertLess(body.index("askConfirm("), body.index("/api/admin/accounts/update-password"))

    def test_removing_a_suspension_asks_in_the_panel_not_with_the_browser_dialog(self):
        body = function_body(self.js, "handleUnbanAccount")
        self.assertIn("askConfirm(", body)
        self.assertNotRegex(body, r"(?<![\w.])confirm\(")

    def test_deleting_a_character_asks_for_the_exact_name_then_posts_it(self):
        body = function_body(self.js, "handleDeleteCharacter")
        self.assertRegex(body, r"typeToConfirm:\s*name")
        self.assertIn("danger: true", body)
        self.assertLess(body.index("askConfirm("), body.index("/api/admin/characters/delete"))
        self.assertIn("role_id: roleId", body)
        self.assertIn("confirm_name: name", body)
        self.assertIn("method: 'POST'", body)

    def test_the_delete_character_button_is_wired_and_hidden_for_admin_accounts(self):
        card = function_body(self.js, "renderCharacterCard")
        self.assertIn("btn-delete-character", card)
        self.assertRegex(card, r"acc\.is_admin|account\.is_admin|isAdminAccount")
        self.assertIn("data-role-name", card)
        self.assertIn("handleDeleteCharacter(target)", self.js)

    def test_the_account_delete_modal_still_asks_for_the_typed_name(self):
        self.assertIn("You must type the account name exactly to confirm.", function_body(self.js, "handleDeleteAccount"))

    def test_no_delete_or_password_path_uses_the_native_confirm(self):
        for name in ("handleUpdatePassword", "handleDeleteAccount", "handleDeleteCharacter", "handleUnbanAccount"):
            self.assertNotRegex(function_body(self.js, name), r"(?<![\w.])confirm\(", name)


class SpanishTest(unittest.TestCase):
    def test_every_new_key_is_translated(self):
        es = json.loads(read("public", "locales", "es.json"))
        for key in ("Delete character", "Change password", "Remove suspension", "Confirm",
                    "Type the exact character name to confirm",
                    "Change the password of account {account}? Active sessions of that account will be signed out.",
                    "This deletes character {name} of account {account}. The character leaves the account; its data stays in the database."):
            self.assertIn(key, es)
            self.assertTrue(es[key].strip())


if __name__ == "__main__":
    unittest.main()
