import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.deadlock.bankers_algorithm import BankersAlgorithm


def build_textbook_scenario():
    """The classic 5-process, 3-resource-type (A, B, C) example from
    Silberschatz/Galvin/Gagne 'Operating System Concepts'.

    Total resources: A=10, B=5, C=7
    """
    task_ids = ["P0", "P1", "P2", "P3", "P4"]

    max_claim = {
        "P0": [7, 5, 3],
        "P1": [3, 2, 2],
        "P2": [9, 0, 2],
        "P3": [2, 2, 2],
        "P4": [4, 3, 3],
    }

    allocation = {
        "P0": [0, 1, 0],
        "P1": [2, 0, 0],
        "P2": [3, 0, 2],
        "P3": [2, 1, 1],
        "P4": [0, 0, 2],
    }

    available = [3, 3, 2]  # total 10,5,7 minus what's already allocated

    return BankersAlgorithm(available, max_claim, allocation, task_ids)


def test_initial_state_is_safe():
    banker = build_textbook_scenario()
    safe, sequence = banker.is_safe_state()
    assert safe, "Textbook initial state must be safe"
    # textbook's canonical safe sequence is <P1, P3, P4, P0, P2>
    assert sequence == ["P1", "P3", "P4", "P0", "P2"], f"Unexpected safe sequence: {sequence}"
    print(f"Initial state SAFE. Safe sequence: {sequence}")


def test_p1_request_1_0_2_is_granted():
    """Textbook: P1 requests (1,0,2). Need_P1=(1,2,2) covers it, and
    available=(3,3,2) covers it. Resulting state is safe -> granted."""
    banker = build_textbook_scenario()
    granted, reason, sequence = banker.request_resources("P1", [1, 0, 2])
    assert granted, f"P1's request should be granted: {reason}"
    assert banker.available == [2, 3, 0], f"Available mismatch after grant: {banker.available}"
    assert banker.allocation["P1"] == [3, 0, 2]
    assert banker.need["P1"] == [0, 2, 0]
    print(f"P1 request (1,0,2) GRANTED. New safe sequence: {sequence}")


def test_p4_request_3_3_0_must_wait():
    """After P1's request is granted, available=(2,3,0). P4 requests
    (3,3,0) -- resource A alone (3 > 2 available) is insufficient, so
    P4 must wait regardless of safety."""
    banker = build_textbook_scenario()
    banker.request_resources("P1", [1, 0, 2])  # apply P1's grant first

    granted, reason, sequence = banker.request_resources("P4", [3, 3, 0])
    assert not granted, "P4's request should be denied (insufficient available resources)"
    assert "Insufficient" in reason
    print(f"P4 request (3,3,0) DENIED: {reason}")


def test_p0_request_0_2_0_denied_unsafe():
    """After P1's request, available=(2,3,0). P0 requests (0,2,0), which
    is within its need and within available -- but granting it leads to
    an UNSAFE state (textbook confirms this), so it must be denied even
    though enough raw resources exist."""
    banker = build_textbook_scenario()
    banker.request_resources("P1", [1, 0, 2])

    pre_available = list(banker.available)
    pre_allocation_p0 = list(banker.allocation["P0"])

    granted, reason, sequence = banker.request_resources("P0", [0, 2, 0])
    assert not granted, "P0's request should be denied (would cause unsafe state)"
    assert "unsafe" in reason

    # state must be rolled back exactly, not left half-applied
    assert banker.available == pre_available, "Available was not rolled back correctly"
    assert banker.allocation["P0"] == pre_allocation_p0, "Allocation was not rolled back correctly"

    print(f"P0 request (0,2,0) DENIED: {reason}")


def test_request_exceeding_declared_max_raises():
    """A task can never validly request more than (max_claim - allocation);
    that's a contract violation, not a resource shortage."""
    banker = build_textbook_scenario()
    try:
        banker.request_resources("P2", [10, 0, 0])  # P2's need is only (6,0,0)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        print(f"Correctly rejected over-claim request: {e}")


def test_release_resources_returns_units():
    banker = build_textbook_scenario()
    before = list(banker.available)
    banker.release_resources("P2", [3, 0, 2])  # P2 releases its full current allocation
    assert banker.allocation["P2"] == [0, 0, 0]
    assert banker.available == [before[i] + [3, 0, 2][i] for i in range(3)]
    print(f"P2 released (3,0,2). New available: {banker.available}")


if __name__ == "__main__":
    test_initial_state_is_safe()
    test_p1_request_1_0_2_is_granted()
    test_p4_request_3_3_0_must_wait()
    test_p0_request_0_2_0_denied_unsafe()
    test_request_exceeding_declared_max_raises()
    test_release_resources_returns_units()
    print("\nALL BANKER'S ALGORITHM TESTS PASSED")