"""Unit tests for rebuild recovery decision logic (Stage 5C.1)."""

from datetime import datetime, timezone

import pytest

from src.logic.rebuild_failure_detection import InconsistencyType, RebuildInconsistency
from src.logic.rebuild_recovery import RecoveryAction, determine_recovery_action

UTC = timezone.utc


@pytest.fixture
def current_time():
    """Current timestamp for testing."""
    return datetime.now(UTC)


@pytest.fixture
def no_inconsistency(current_time):
    """Rebuild inconsistency with type NONE."""
    return RebuildInconsistency(
        inconsistency_type=InconsistencyType.NONE,
        job_id="test-job-1",
        reason="No inconsistency detected",
        detected_at=current_time,
    )


@pytest.fixture
def orphaned_inconsistency(current_time):
    """Rebuild inconsistency with type ORPHANED_RUNNING."""
    return RebuildInconsistency(
        inconsistency_type=InconsistencyType.ORPHANED_RUNNING,
        job_id="test-job-1",
        reason="Job running in DB but no executor in runtime",
        detected_at=current_time,
    )


@pytest.fixture
def crash_inconsistency(current_time):
    """Rebuild inconsistency with type CRASH_SUSPICION."""
    return RebuildInconsistency(
        inconsistency_type=InconsistencyType.CRASH_SUSPICION,
        job_id="test-job-1",
        reason="Worker has stale heartbeat",
        detected_at=current_time,
    )


@pytest.fixture
def zombie_inconsistency(current_time):
    """Rebuild inconsistency with type ZOMBIE_EXECUTOR."""
    return RebuildInconsistency(
        inconsistency_type=InconsistencyType.ZOMBIE_EXECUTOR,
        job_id="test-job-1",
        reason="Runtime has active executor but DB is not running",
        detected_at=current_time,
    )


@pytest.fixture
def stale_inconsistency(current_time):
    """Rebuild inconsistency with type STALE_OWNERSHIP."""
    return RebuildInconsistency(
        inconsistency_type=InconsistencyType.STALE_OWNERSHIP,
        job_id="test-job-1",
        reason="Ownership stale (heartbeat exceeds TTL)",
        detected_at=current_time,
    )


class TestDetermineRecoveryActionDeterminism:
    """Test determinism of recovery decision function."""

    def test_same_inputs_produce_same_outputs(self, no_inconsistency):
        """Same inputs should always produce same outputs."""
        decision1 = determine_recovery_action(no_inconsistency, lock_is_valid=True)
        decision2 = determine_recovery_action(no_inconsistency, lock_is_valid=True)
        decision3 = determine_recovery_action(no_inconsistency, lock_is_valid=True)

        assert decision1.action == decision2.action == decision3.action
        assert decision1.reason == decision2.reason == decision3.reason
        assert decision1.safe_to_execute == decision2.safe_to_execute == decision3.safe_to_execute

    def test_all_combinations_are_deterministic(
        self,
        no_inconsistency,
        orphaned_inconsistency,
        zombie_inconsistency,
        crash_inconsistency,
        stale_inconsistency,
    ):
        """All input combinations should be deterministic."""
        inconsistencies = [
            no_inconsistency,
            orphaned_inconsistency,
            zombie_inconsistency,
            crash_inconsistency,
            stale_inconsistency,
        ]
        lock_states = [True, False]

        for inc in inconsistencies:
            for lock_valid in lock_states:
                d1 = determine_recovery_action(inc, lock_is_valid=lock_valid)
                d2 = determine_recovery_action(inc, lock_is_valid=lock_valid)
                assert d1.action == d2.action
                assert d1.reason == d2.reason
                assert d1.safe_to_execute == d2.safe_to_execute


class TestNoInconsistencyDecisions:
    """Tests for recovery decisions when no inconsistency is detected."""

    def test_resume_when_no_inconsistency_and_lock_valid(self, no_inconsistency):
        """Should RESUME when no inconsistency and lock is valid."""
        decision = determine_recovery_action(no_inconsistency, lock_is_valid=True)

        assert decision.action == RecoveryAction.RESUME
        assert decision.safe_to_execute is True
        assert "No inconsistency" in decision.reason
        assert "lock is valid" in decision.reason

    def test_wait_when_no_inconsistency_but_lock_invalid(self, no_inconsistency):
        """Should WAIT when no inconsistency but lock is not valid."""
        decision = determine_recovery_action(no_inconsistency, lock_is_valid=False)

        assert decision.action == RecoveryAction.WAIT
        assert decision.safe_to_execute is False
        assert "lock is not valid" in decision.reason


class TestOrphanedRunningDecisions:
    """Tests for recovery decisions when orphaned running state is detected."""

    def test_unsafe_when_orphaned_with_valid_lock(self, orphaned_inconsistency):
        """Should be UNSAFE when orphaned state detected while holding lock."""
        decision = determine_recovery_action(orphaned_inconsistency, lock_is_valid=True)

        assert decision.action == RecoveryAction.UNSAFE
        assert decision.safe_to_execute is False
        assert "split-brain" in decision.reason.lower()
        assert "unsafe" in decision.reason.lower()

    def test_reset_when_orphaned_without_lock(self, orphaned_inconsistency):
        """Should RESET when orphaned state detected without lock."""
        decision = determine_recovery_action(orphaned_inconsistency, lock_is_valid=False)

        assert decision.action == RecoveryAction.RESET
        assert decision.safe_to_execute is False
        assert "reset" in decision.reason.lower()


class TestCrashSuspicionDecisions:
    """Tests for recovery decisions when crash is suspected."""

    def test_wait_when_crash_suspected_with_valid_lock(self, crash_inconsistency):
        """Should WAIT when crash suspected but lock still valid."""
        decision = determine_recovery_action(crash_inconsistency, lock_is_valid=True)

        assert decision.action == RecoveryAction.WAIT
        assert decision.safe_to_execute is False
        assert "wait for lock expiry" in decision.reason.lower()

    def test_reset_when_crash_suspected_without_lock(self, crash_inconsistency):
        """Should RESET when crash suspected and lock expired."""
        decision = determine_recovery_action(crash_inconsistency, lock_is_valid=False)

        assert decision.action == RecoveryAction.RESET
        assert decision.safe_to_execute is False
        assert "reset" in decision.reason.lower()


class TestZombieExecutorDecisions:
    """Tests for recovery decisions when zombie executor state is detected."""

    def test_unsafe_when_zombie_with_valid_lock(self, zombie_inconsistency):
        """Should be UNSAFE when runtime executor is active but DB is not running."""
        decision = determine_recovery_action(zombie_inconsistency, lock_is_valid=True)
        assert decision.action == RecoveryAction.UNSAFE
        assert decision.safe_to_execute is False

    def test_unsafe_when_zombie_without_valid_lock(self, zombie_inconsistency):
        """Should remain UNSAFE even without a valid lock."""
        decision = determine_recovery_action(zombie_inconsistency, lock_is_valid=False)
        assert decision.action == RecoveryAction.UNSAFE
        assert decision.safe_to_execute is False


class TestStaleOwnershipDecisions:
    """Tests for recovery decisions when stale ownership is detected."""

    def test_wait_when_stale_ownership_with_valid_lock(self, stale_inconsistency):
        """Should WAIT when stale ownership but lock still valid (transitional)."""
        decision = determine_recovery_action(stale_inconsistency, lock_is_valid=True)

        assert decision.action == RecoveryAction.WAIT
        assert decision.safe_to_execute is False
        assert "wait for state stabilization" in decision.reason.lower()

    def test_reset_when_stale_ownership_without_lock(self, stale_inconsistency):
        """Should RESET when stale ownership and lock expired."""
        decision = determine_recovery_action(stale_inconsistency, lock_is_valid=False)

        assert decision.action == RecoveryAction.RESET
        assert decision.safe_to_execute is False
        assert "reset" in decision.reason.lower()


class TestSafeToExecuteFlag:
    """Tests for safe_to_execute flag correctness."""

    def test_only_resume_is_safe_to_execute(
        self,
        no_inconsistency,
        orphaned_inconsistency,
        zombie_inconsistency,
        crash_inconsistency,
        stale_inconsistency,
    ):
        """Only RESUME action should have safe_to_execute=True."""
        # RESUME case
        decision_resume = determine_recovery_action(no_inconsistency, lock_is_valid=True)
        assert decision_resume.action == RecoveryAction.RESUME
        assert decision_resume.safe_to_execute is True

        # All other cases should be False
        unsafe_decisions = [
            determine_recovery_action(no_inconsistency, lock_is_valid=False),
            determine_recovery_action(orphaned_inconsistency, lock_is_valid=True),
            determine_recovery_action(orphaned_inconsistency, lock_is_valid=False),
            determine_recovery_action(zombie_inconsistency, lock_is_valid=True),
            determine_recovery_action(zombie_inconsistency, lock_is_valid=False),
            determine_recovery_action(crash_inconsistency, lock_is_valid=True),
            determine_recovery_action(crash_inconsistency, lock_is_valid=False),
            determine_recovery_action(stale_inconsistency, lock_is_valid=True),
            determine_recovery_action(stale_inconsistency, lock_is_valid=False),
        ]

        for decision in unsafe_decisions:
            assert decision.safe_to_execute is False


class TestRecoveryActionPriority:
    """Tests for recovery action priority (UNSAFE > RESET > WAIT > RESUME)."""

    def test_unsafe_is_highest_priority(self, orphaned_inconsistency):
        """UNSAFE action should be used for split-brain conditions."""
        decision = determine_recovery_action(orphaned_inconsistency, lock_is_valid=True)
        assert decision.action == RecoveryAction.UNSAFE

    def test_reset_for_recoverable_failures_without_lock(
        self, orphaned_inconsistency, crash_inconsistency, stale_inconsistency
    ):
        """RESET should be used for recoverable failures without lock."""
        for inconsistency in [
            orphaned_inconsistency,
            crash_inconsistency,
            stale_inconsistency,
        ]:
            decision = determine_recovery_action(inconsistency, lock_is_valid=False)
            assert decision.action == RecoveryAction.RESET

    def test_wait_for_transitional_states(self, crash_inconsistency, stale_inconsistency):
        """WAIT should be used for transitional states with valid lock."""
        for inconsistency in [crash_inconsistency, stale_inconsistency]:
            decision = determine_recovery_action(inconsistency, lock_is_valid=True)
            assert decision.action == RecoveryAction.WAIT

    def test_resume_only_when_safe(self, no_inconsistency):
        """RESUME should only be used when truly safe."""
        decision = determine_recovery_action(no_inconsistency, lock_is_valid=True)
        assert decision.action == RecoveryAction.RESUME


class TestInconsistencyTypeTracking:
    """Tests that inconsistency type is preserved in decision."""

    def test_inconsistency_type_is_included_in_decision(
        self,
        no_inconsistency,
        orphaned_inconsistency,
        zombie_inconsistency,
        crash_inconsistency,
        stale_inconsistency,
    ):
        """Inconsistency type should be preserved in decision."""
        inconsistencies = [
            (no_inconsistency, InconsistencyType.NONE),
            (orphaned_inconsistency, InconsistencyType.ORPHANED_RUNNING),
            (zombie_inconsistency, InconsistencyType.ZOMBIE_EXECUTOR),
            (crash_inconsistency, InconsistencyType.CRASH_SUSPICION),
            (stale_inconsistency, InconsistencyType.STALE_OWNERSHIP),
        ]

        for inconsistency, expected_type in inconsistencies:
            decision = determine_recovery_action(inconsistency, lock_is_valid=True)
            assert decision.inconsistency_type == expected_type
