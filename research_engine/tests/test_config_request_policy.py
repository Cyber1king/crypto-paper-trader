"""Phase 28A: one numeric-input policy across all three configuration endpoints.

**The problem this file records.** Three paper modes accept a configuration number
over HTTP, and they did not agree on what a number *is*:

=========================  ==================================  ==========================
endpoint                   field                              before Phase 28A
=========================  ==================================  ==========================
``POST /api/high-risk/config``  ``risk_fraction``               refused a quoted number
``POST /api/manual/action``     ``size_pct``                   accepted a quoted number
``POST /api/daily-target/config``  ``target_amount``           accepted a quoted number
=========================  ==================================  ==========================

Pydantic's default is *lax*: ``"0.5"`` becomes the float ``0.5``. So the same request
body was a 422 on one endpoint and a 200 on another. Nothing unsafe resulted -
every value still passed the engine's own finite / ``>0`` / ``<=1.0`` check, and a
``bool`` was refused everywhere - but a client could not know which rule applied
without trying it, and the refusal/acceptance split was an accident of which phase
wrote the endpoint last rather than a decision anyone made.

**The policy now applied, identically on all three:** accept JSON *numbers* only.
A boolean is refused, and a quoted number is refused, because each field has exactly
one correct wire representation and a silent second one means the API and the UI
could disagree about what was actually configured. This file is the executable
statement of that policy; the three schemas each point at it.

The numeric bounds themselves are unchanged and remain owned by the engine, which
is what rejects ``nan``, ``inf``, ``<= 0`` and anything above each mode's ceiling.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from crypto_paper_lab.daily_target import DEFAULT_TARGET_AMOUNT
from crypto_paper_lab.high_risk import DEFAULT_RISK_FRACTION
from paper_api.app import create_app
from paper_api.moderegistry import ModeRegistry

# (endpoint, extra body fields, the number field, a legal in-range example)
CONFIG_ENDPOINTS = [
    ("/api/high-risk/config", {}, "risk_fraction", 0.5),
    ("/api/manual/action", {"action": "ENTER_LONG"}, "size_pct", 0.5),
    ("/api/daily-target/config", {}, "target_amount", 100.0),
]

# Values that are NOT JSON numbers. A quoted number, a boolean, and the strings a
# JSON client might send for a non-finite number.
NOT_JSON_NUMBERS = [
    "0.5",          # a well-formed quoted number - the case that differed
    "1",
    "50",
    " 0.5 ",
    "0.5abc",
    "NaN",
    "Infinity",
    "-Infinity",
    "",
    "   ",
]


def client_for() -> TestClient:
    """A client over a fresh registry, so each test starts from known state."""

    return TestClient(create_app(registry=ModeRegistry()))


def post_config(client: TestClient, endpoint: str, extra: dict, field: str, value):
    return client.post(endpoint, json={**extra, field: value})


def non_finite_body(extra: dict, field: str, literal: str) -> str:
    """Well-formed JSON whose ``field`` holds a bare NaN/Infinity literal.

    ``json.dumps`` cannot express these constants - it would emit ``null`` or
    raise - so the literal has to be spliced in by hand. Splicing it into a
    hand-written format string is what produced the original bug: ``'{**%s,
    "%s": NaN}'`` emits Python's single-quoted dict and a ``**`` spread, neither
    of which is JSON, so the server refused the body at the *parser* and the
    test never reached a field validator.

    So the object is encoded by ``json.dumps`` - which handles quoting, commas
    and key order correctly for both the empty and non-empty cases - using a
    sentinel string as a placeholder, and only the placeholder is then replaced
    with the bare literal. The result is guaranteed parseable.
    """
    sentinel = "@@NON_FINITE@@"
    body = dict(extra)
    body[field] = sentinel

    return json.dumps(body).replace(f'"{sentinel}"', literal)


class TestNumericInputPolicyIsUniform:
    """The rule that Phase 28A adopted: JSON numbers only, on all three endpoints."""

    @pytest.mark.parametrize("endpoint,extra,field,_legal", CONFIG_ENDPOINTS)
    @pytest.mark.parametrize("value", NOT_JSON_NUMBERS)
    def test_a_quoted_or_boolean_value_is_refused_everywhere(
        self, endpoint, extra, field, _legal, value
    ) -> None:
        client = client_for()

        response = post_config(client, endpoint, extra, field, value)

        assert response.status_code == 422, (
            f"{endpoint} accepted {field}={value!r} with "
            f"{response.status_code}; the policy is JSON numbers only"
        )

    @pytest.mark.parametrize("endpoint,extra,field,_legal", CONFIG_ENDPOINTS)
    @pytest.mark.parametrize("value", [True, False])
    def test_a_boolean_is_refused_everywhere(
        self, endpoint, extra, field, _legal, value
    ) -> None:
        # A boolean is a *type*, not a number, and Python treats `bool` as a
        # subclass of `int`, so Pydantic would quietly coerce it to the number
        # 1.0 instead of rejecting it. The policy therefore refuses one
        # uniformly, on every field, without claiming what 1.0 means to any
        # particular one: it is the ceiling for the two fraction fields, and a
        # trivial dollar amount for `target_amount`, whose ceiling is far
        # higher. What matters is that no field silently accepts a "yes" where
        # a number was expected.
        client = client_for()

        response = post_config(client, endpoint, extra, field, value)

        assert response.status_code == 422, (
            f"{endpoint} accepted the boolean {field}={value!r}"
        )

    @pytest.mark.parametrize("endpoint,extra,field,legal", CONFIG_ENDPOINTS)
    def test_a_real_json_number_is_still_accepted(
        self, endpoint, extra, field, legal
    ) -> None:
        """The policy narrows what a *number* may look like; it must not narrow
        the set of legal numbers."""

        client = client_for()

        response = post_config(client, endpoint, extra, field, legal)

        assert response.status_code == 200, (
            f"{endpoint} refused the legal number {field}={legal!r}: "
            f"{response.status_code} {response.text[:200]}"
        )

    @pytest.mark.parametrize("endpoint,extra,field,_legal", CONFIG_ENDPOINTS)
    def test_an_integer_is_still_accepted_as_a_number(
        self, endpoint, extra, field, _legal
    ) -> None:
        """JSON has one number type; an int body must not be treated as a
        different kind of value from a float body."""

        client = client_for()

        response = post_config(client, endpoint, extra, field, 1)

        assert response.status_code == 200, (
            f"{endpoint} refused the integer 1 for {field}: {response.status_code}"
        )


class TestThePolicyDidNotWeakenAnyBound:
    """Rejection order matters: the engine still owns every numeric bound."""

    @pytest.mark.parametrize(
        "endpoint,extra,field,bad",
        [
            ("/api/high-risk/config", {}, "risk_fraction", 1.01),
            ("/api/high-risk/config", {}, "risk_fraction", 0),
            ("/api/high-risk/config", {}, "risk_fraction", -0.5),
            ("/api/manual/action", {"action": "ENTER_LONG"}, "size_pct", 1.01),
            ("/api/manual/action", {"action": "ENTER_LONG"}, "size_pct", 0),
            ("/api/manual/action", {"action": "ENTER_LONG"}, "size_pct", -1.0),
            ("/api/daily-target/config", {}, "target_amount", 0),
            ("/api/daily-target/config", {}, "target_amount", -5.0),
            ("/api/daily-target/config", {}, "target_amount", 1e12),
        ],
    )
    def test_out_of_range_is_still_refused_with_422(
        self, endpoint, extra, field, bad
    ) -> None:
        client = client_for()

        response = post_config(client, endpoint, extra, field, bad)

        assert response.status_code == 422, (
            f"{endpoint} accepted {field}={bad!r} with {response.status_code}"
        )

    @pytest.mark.parametrize(
        "endpoint,extra,field", [
            ("/api/high-risk/config", {}, "risk_fraction"),
            ("/api/manual/action", {"action": "ENTER_LONG"}, "size_pct"),
            ("/api/daily-target/config", {}, "target_amount"),
        ]
    )
    def test_non_finite_numbers_are_still_refused(
        self, endpoint, extra, field
    ) -> None:
        """A non-finite literal must be refused by the *engine's* finite check.

        The body has to be well-formed JSON carrying a bare ``NaN`` /
        ``Infinity`` / ``-Infinity``, which ``json.dumps`` cannot produce and
        which a naive format string gets wrong: ``'{**%s, "%s": NaN}'`` emits
        single-quoted keys and a ``**`` spread, which is not JSON at all. The
        server then refuses it at the *parser* with ``json_invalid``, so a test
        that only asserts ``422`` would pass without ever reaching a field
        validator - and would still pass if the engine's finite check were
        deleted. That is exactly the bug this test previously had.

        ``json.loads`` accepts these bare constants, and so does this API's
        parser, so a well-formed body does reach the engine. The assertions
        below therefore pin down *which layer* refused:

        * ``422`` - refused, as required;
        * ``detail.code == "VALIDATION_ERROR"`` - a *validation* refusal, not a
          parse failure, which would carry ``detail.type == "json_invalid"``;
        * ``"finite" in detail.message`` - the engine's own wording, which is
          what proves the value travelled through the transport.
        """
        for literal in ("NaN", "Infinity", "-Infinity"):
            client = client_for()
            before = client.get(f"/api/{endpoint.split('/')[2]}").json()
            body = non_finite_body(extra, field, literal)

            # The body must be parseable, or this test proves nothing.
            json.loads(body)

            response = client.post(
                endpoint,
                content=body.encode("utf-8"),
                headers={"content-type": "application/json"},
            )
            detail = response.json().get("detail", {})

            assert response.status_code == 422, (
                f"{endpoint} accepted {field}={literal} with "
                f"{response.status_code}"
            )
            assert detail.get("code") == "VALIDATION_ERROR", (
                f"{endpoint} refused {field}={literal} at the JSON parser "
                f"({detail!r}) rather than at the engine's finite check, so "
                f"this request never exercised the bound it claims to test"
            )
            assert "finite" in detail.get("message", ""), (
                f"{endpoint} did not use the engine's own wording for "
                f"{field}={literal}: {detail.get('message')!r}"
            )
            assert client.get(f"/api/{endpoint.split('/')[2]}").json() == before, (
                f"{endpoint} changed state after refusing {field}={literal}"
            )

    @pytest.mark.parametrize(
        "endpoint,extra,field", [
            ("/api/high-risk/config", {}, "risk_fraction"),
            ("/api/manual/action", {"action": "ENTER_LONG"}, "size_pct"),
            ("/api/daily-target/config", {}, "target_amount"),
        ]
    )
    def test_a_missing_field_is_still_refused(self, endpoint, extra, field) -> None:
        client = client_for()

        response = client.post(endpoint, json=dict(extra))

        assert response.status_code == 422

    @pytest.mark.parametrize(
        "endpoint,extra,field,legal", CONFIG_ENDPOINTS
    )
    def test_an_extra_field_is_still_refused(self, endpoint, extra, field, legal) -> None:
        # extra="forbid" is part of the contract: an unknown key must not be
        # silently ignored.
        client = client_for()

        response = post_config(client, endpoint, extra, field, legal)
        assert response.status_code == 200

        response = client.post(
            endpoint, json={**extra, field: legal, "not_a_field": 1}
        )
        assert response.status_code == 422, (
            f"{endpoint} accepted an unknown field"
        )


class TestARefusalChangesNothing:
    """A rejected configuration must leave the mode's whole state untouched."""

    def _snapshot(self, client: TestClient, mode: str) -> dict:
        return client.get(f"/api/{mode.replace('_', '-')}").json()

    def test_high_risk_refusals_leave_state_identical(self) -> None:
        client = client_for()
        before = self._snapshot(client, "high_risk")

        for bad in ("0.5", "50", True, 1.01, 0, -1.0):
            post_config(client, "/api/high-risk/config", {}, "risk_fraction", bad)

        assert self._snapshot(client, "high_risk") == before

    def test_daily_target_refusals_leave_state_identical(self) -> None:
        client = client_for()
        # Set a non-default target first so a silent overwrite would be visible.
        assert client.post(
            "/api/daily-target/config", json={"target_amount": 100.0}
        ).status_code == 200
        before = self._snapshot(client, "daily_target")

        for bad in ("100", "abc", True, 0, -5.0, 1e12):
            post_config(client, "/api/daily-target/config", {}, "target_amount", bad)

        assert self._snapshot(client, "daily_target") == before
        assert before["daily_target_amount"] == 100.0

    def test_manual_refusals_leave_state_identical(self) -> None:
        client = client_for()
        # Establish a pending action, then prove a refused one does not replace it.
        assert client.post(
            "/api/manual/action", json={"action": "ENTER_LONG", "size_pct": 0.25}
        ).status_code == 200
        before = self._snapshot(client, "manual")
        assert before["pending_action"]["size_pct"] == 0.25

        for bad in ("0.5", "abc", True, 1.01, 0, -1.0):
            post_config(
                client, "/api/manual/action", {"action": "ENTER_SHORT"}, "size_pct", bad
            )

        after = self._snapshot(client, "manual")
        assert after == before
        assert after["pending_action"]["size_pct"] == 0.25

    def test_a_refusal_never_commits_capital(self) -> None:
        """No refusal path may move any mode's account.

        The risk this guards is a silent type coercion: a boolean, which Python
        treats as a subclass of ``int``, becoming the number ``1.0`` and being
        taken for a size the user actually asked for. The severity differs by
        field - ``1.0`` is the whole account for the two fraction fields, and a
        negligible dollar amount for ``target_amount`` - so the check below
        does not reason about what ``1.0`` means. It asserts the stronger,
        field-agnostic property: after any refused request the account is
        byte-for-byte what it was."""

        client = client_for()

        for endpoint, extra, field in (
            ("/api/high-risk/config", {}, "risk_fraction"),
            ("/api/manual/action", {"action": "ENTER_LONG"}, "size_pct"),
            ("/api/daily-target/config", {}, "target_amount"),
        ):
            before = client.get("/api/account?mode=" + (
                "high_risk" if "high-risk" in endpoint
                else "manual" if "manual" in endpoint
                else "daily_target"
            )).json()

            post_config(client, endpoint, extra, field, True)
            post_config(client, endpoint, extra, field, "1")
            post_config(client, endpoint, extra, field, "100")

            after = client.get("/api/account?mode=" + (
                "high_risk" if "high-risk" in endpoint
                else "manual" if "manual" in endpoint
                else "daily_target"
            )).json()

            assert after == before, f"{endpoint} changed account state on a refusal"
            assert after["balance"] == 10000.0


class TestDefaultsAreUnchanged:
    """Phase 28A changed input *spelling*, never a default or a bound."""

    def test_high_risk_default_is_still_a_quarter(self) -> None:
        client = client_for()

        state = client.get("/api/high-risk").json()

        assert state["risk_fraction"] == DEFAULT_RISK_FRACTION == 0.25
        assert state["max_risk_fraction"] == 1.0

    def test_daily_target_default_is_still_fifty_dollars(self) -> None:
        client = client_for()

        state = client.get("/api/daily-target").json()

        assert state["daily_target_amount"] == DEFAULT_TARGET_AMOUNT == 50.0

    def test_the_largest_legal_value_is_still_one(self) -> None:
        """1.0 is the engine's ceiling and the boundary between sizing and
        leverage. A quoted "1.0" must not become a way to reach it."""

        client = client_for()

        assert client.post(
            "/api/high-risk/config", json={"risk_fraction": 1.0}
        ).status_code == 200
        assert client.get("/api/high-risk").json()["risk_fraction"] == 1.0

        assert client.post(
            "/api/high-risk/config", json={"risk_fraction": "1.0"}
        ).status_code == 422
        assert client.get("/api/high-risk").json()["risk_fraction"] == 1.0


class TestNoValidNumberWasNarrowed:
    """Regression guard: the legal numeric space is byte-for-byte what it was."""

    @pytest.mark.parametrize("value", [0.01, 0.1, 0.25, 0.5, 0.99, 1, 1.0])
    def test_high_risk_accepts_every_legal_risk_fraction(self, value) -> None:
        client = client_for()

        response = client.post(
            "/api/high-risk/config", json={"risk_fraction": value}
        )

        assert response.status_code == 200, response.text[:200]
        assert client.get("/api/high-risk").json()["risk_fraction"] == float(value)

    @pytest.mark.parametrize("value", [1.0, 10.0, 20.0, 50.0, 100.0, 1000.0, 1e6])
    def test_daily_target_accepts_every_legal_amount(self, value) -> None:
        client = client_for()

        response = client.post(
            "/api/daily-target/config", json={"target_amount": value}
        )

        assert response.status_code == 200, response.text[:200]
        assert client.get("/api/daily-target").json()["daily_target_amount"] == float(value)

    @pytest.mark.parametrize("value", [0.01, 0.25, 0.5, 1, 1.0])
    def test_manual_accepts_every_legal_size(self, value) -> None:
        client = client_for()

        response = client.post(
            "/api/manual/action", json={"action": "ENTER_LONG", "size_pct": value}
        )

        assert response.status_code == 200, response.text[:200]

    def test_nan_and_infinity_are_not_reachable_as_strings_either(self) -> None:
        """Before Phase 28A these were refused by the *engine* after Pydantic
        coerced the string into a float. They are now refused at the edge. Both
        were 422; the state is unchanged either way, which is what matters."""

        client = client_for()
        client.post("/api/daily-target/config", json={"target_amount": 100.0})
        before = client.get("/api/daily-target").json()

        for literal in ("NaN", "Infinity", "-Infinity"):
            assert client.post(
                "/api/daily-target/config", json={"target_amount": literal}
            ).status_code == 422

        assert client.get("/api/daily-target").json() == before
        assert before["daily_target_amount"] == 100.0

    def test_an_overflowing_float_literal_is_refused_by_the_engine(self) -> None:
        """``1e400`` is *valid* JSON and parses to infinity, so unlike a bare
        ``NaN`` it needs no non-standard literal to reach the engine.

        That makes it the cleanest way to prove the engine's finite check is
        still the authoritative bound on this path: the transport validator has
        no reason to touch an ordinary JSON number, so the only thing that can
        refuse ``inf`` is the engine.
        """

        client = client_for()
        client.post("/api/daily-target/config", json={"target_amount": 100.0})
        before = client.get("/api/daily-target").json()

        response = client.post(
            "/api/daily-target/config",
            content=b'{"target_amount": 1e400}',
            headers={"content-type": "application/json"},
        )
        detail = response.json().get("detail", {})

        assert response.status_code == 422
        assert detail.get("code") == "VALIDATION_ERROR", (
            f"refused at the wrong layer: {detail!r}"
        )
        assert "finite" in detail.get("message", ""), (
            f"expected the engine's own finite wording, got "
            f"{detail.get('message')!r}"
        )
        assert client.get("/api/daily-target").json() == before
        assert before["daily_target_amount"] == 100.0