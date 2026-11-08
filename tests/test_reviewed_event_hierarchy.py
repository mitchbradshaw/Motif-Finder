from scripts.thesis.reviewed_event_hierarchy import associate, peak_identity


def test_two_events_keep_distinct_identities_despite_shared_recovery_context():
    peaks=[dict(peak_idx=10,start_idx=0,end_idx=22),dict(peak_idx=20,start_idx=8,end_idx=30)]
    assert associate(0,30,peaks,1)==[0,1]
    assert peak_identity(1,10,-1)!=peak_identity(1,20,-1)
    # Multiple parents can support the same child, without creating another event.
    assert associate(8,14,peaks,1)==[0]
    assert peak_identity(1,10,-1)==peak_identity(1,10,-1)
    assert peak_identity(2,10,-1)!=peak_identity(1,10,-1)


def test_fragment_fallback_does_not_jump_to_a_distant_neighbour():
    peaks=[dict(peak_idx=10,start_idx=5,end_idx=30)]
    assert associate(15,25,peaks,1)==[0]
    assert associate(90,100,peaks,1)==[]
