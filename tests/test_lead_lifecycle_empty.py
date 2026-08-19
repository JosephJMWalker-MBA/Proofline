from proofline.lead_lifecycle import LeadLifecycle


def test_empty_lead_lifecycle_initializes_without_inventing_state(tmp_path) -> None:
    lifecycle = LeadLifecycle(tmp_path / "state")
    assert lifecycle.store.status()["leads"] == 0
    assert lifecycle.review_history("lead:does-not-exist") == ()
    assert lifecycle.get("lead:does-not-exist") is None
    assert lifecycle.package_candidate_observations() == ()
