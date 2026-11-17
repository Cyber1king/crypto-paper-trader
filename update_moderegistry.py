import os

with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\src\paper_api\moderegistry.py', 'r') as f:
    content = f.read()

# First occurrence (AiSession)
old1 = """load_research_candles(),
                    config=baseline_config(),
                    costs=phase13_costs(),
                    # The policy still has to be passed, because it is what the
                    # replay asks before opening. IntelligencePolicy refuses every
                    # entry - its score gate is evaluated by the book, which owns
                    # the positions - so this replay's own broker stays flat and
                    # the book is the single owner of AI state. See AiSession.
                    policy=IntelligencePolicy(
                        threshold=DEFAULT_THRESHOLD,
                        position_limit=DEFAULT_MAX_POSITIONS,
                    ),
                    dataset_sha256=dataset_identity(),
                """"

new1 = """load_research_candles(dataset_path),
                    config=baseline_config(),
                    costs=phase13_costs(),
                    # The policy still has to be passed, because it is what the
                    # replay asks before opening. IntelligencePolicy refuses every
                    # entry - its score gate is evaluated by the book, which owns
                    # the positions - so this replay's own broker stays flat and
                    # the book is the single owner of AI state. See AiSession.
                    policy=IntelligencePolicy(
                        threshold=DEFAULT_THRESHOLD,
                        position_limit=DEFAULT_MAX_POSITIONS,
                    ),
                    dataset_sha256=dataset_identity(),
                """"

content = content.replace(old1, new1)

# Second occurrence (DailyTargetSession)
old2 = """load_research_candles(),
                    config=baseline_config(),
                    costs=phase13_costs(),
                    policy=DAILY_TARGET_POLICY,
                    dataset_sha256=dataset_identity(),
                    # Injected rather than imported, so the replay holds no reference
                    # to the tracker. Reads a **live** comparison against cash, not the
                    # tracker's latch, so a target crossed by this step's own close is
                    # visible to this step's entry check. See ``daily_target_reached``.
                    daily_target=lambda: tracker.reached_for(
                        session.replay.broker.cash
                    ),"""

new2 = """load_research_candles(dataset_path),
                    config=baseline_config(),
                    costs=phase13_costs(),
                    policy=DAILY_TARGET_POLICY,
                    dataset_sha256=dataset_identity(),
                    # Injected rather than imported, so the replay holds no reference
                    # to the tracker. Reads a **live** comparison against cash, not the
                    # tracker's latch, so a target crossed by this step's own close is
                    # visible to this step's entry check. See ``daily_target_reached``.
                    daily_target=lambda: tracker.reached_for(
                        session.replay.broker.cash
                    ),"""

content = content.replace(old2, new2)

with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\research_engine\src\paper_api\moderegistry.py', 'w') as f:
    f.write(content)

print('moderegistry.py updated')