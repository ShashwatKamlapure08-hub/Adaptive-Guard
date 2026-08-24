def merge_gantt_slices(raw_slices):
    """Merge consecutive (pid, start, end) unit-slices belonging to the same
    task into single contiguous blocks.

    e.g. [("P1",0,1), ("P1",1,2), ("P2",2,3)] -> [("P1",0,2), ("P2",2,3)]

    Used by preemptive algorithms (SRTF, RR) which are simulated one time
    unit at a time and need their raw per-tick execution log collapsed into
    a readable Gantt chart.
    """
    if not raw_slices:
        return []

    merged = [list(raw_slices[0])]  # [pid, start, end]

    for pid, start, end in raw_slices[1:]:
        last = merged[-1]
        if pid == last[0] and start == last[2]:
            last[2] = end  # extend the current block
        else:
            merged.append([pid, start, end])

    return [tuple(block) for block in merged]