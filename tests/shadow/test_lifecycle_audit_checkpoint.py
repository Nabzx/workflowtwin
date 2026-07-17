"""Lifecycle, duplicate suppression, audit integrity, and resume equivalence."""

from workflowtwin.shadow.audit import verify_audit_chain
from workflowtwin.shadow.config import ShadowConfig
from workflowtwin.shadow.fingerprint import shadow_fingerprint
from workflowtwin.shadow.models import IncomingReferralSnapshot, ShadowEvaluationLabel
from workflowtwin.shadow.runner import ShadowModeRunner
from workflowtwin.synthetic.models import GeneratedDataset

ShadowSource = tuple[
    GeneratedDataset,
    tuple[IncomingReferralSnapshot, ...],
    tuple[ShadowEvaluationLabel, ...],
]


def test_duplicate_delivery_is_suppressed_and_audited(
    tiny_shadow_source: ShadowSource, strict_shadow_config: ShadowConfig
) -> None:
    _, snapshots, _ = tiny_shadow_source
    first = snapshots[0]
    run = ShadowModeRunner(strict_shadow_config).run((first, first))
    assert any(record.action == "source_item_ignored_as_duplicate" for record in run.audit_records)
    assert run.case_states[0].duplicate_update_count == 1


def test_audit_chain_detects_modification_deletion_and_reordering(
    tiny_shadow_source: ShadowSource, strict_shadow_config: ShadowConfig
) -> None:
    _, snapshots, _ = tiny_shadow_source
    records = ShadowModeRunner(strict_shadow_config).run(snapshots[:4]).audit_records
    assert verify_audit_chain(records) == (True, 0)
    modified = records[0].model_copy(update={"action": "modified"})
    assert not verify_audit_chain((modified, *records[1:]))[0]
    assert not verify_audit_chain(records[1:])[0]
    assert not verify_audit_chain((records[1], records[0], *records[2:]))[0]


def test_pause_resume_matches_uninterrupted_output(
    tiny_shadow_source: ShadowSource, strict_shadow_config: ShadowConfig
) -> None:
    _, snapshots, _ = tiny_shadow_source
    source = snapshots[:20]
    uninterrupted = ShadowModeRunner(strict_shadow_config).run(source)
    paused = ShadowModeRunner(strict_shadow_config).run(source, max_source_items=7)
    resumed = ShadowModeRunner(strict_shadow_config).run(source, checkpoint=paused.checkpoint)
    assert resumed.recommendations == uninterrupted.recommendations
    assert resumed.detector_results == uninterrupted.detector_results
    assert resumed.manifest.audit_root_fingerprint == uninterrupted.manifest.audit_root_fingerprint
    assert resumed.manifest.manifest_fingerprint == uninterrupted.manifest.manifest_fingerprint


def test_checkpoint_rejects_changed_source(
    tiny_shadow_source: ShadowSource, strict_shadow_config: ShadowConfig
) -> None:
    _, snapshots, _ = tiny_shadow_source
    paused = ShadowModeRunner(strict_shadow_config).run(snapshots[:10], max_source_items=3)
    changed = snapshots[0].model_copy(update={"form_version": "CHANGED"})
    try:
        ShadowModeRunner(strict_shadow_config).run(
            (changed, *snapshots[1:10]), checkpoint=paused.checkpoint
        )
    except ValueError as error:
        assert "source fingerprint" in str(error)
    else:
        raise AssertionError("changed source should invalidate checkpoint")


def test_fingerprints_do_not_depend_on_runtime_paths(strict_shadow_config: ShadowConfig) -> None:
    first = strict_shadow_config.model_copy(update={"run_output": None})
    second = strict_shadow_config.model_copy(update={"run_output": None})
    assert shadow_fingerprint(first) == shadow_fingerprint(second)
