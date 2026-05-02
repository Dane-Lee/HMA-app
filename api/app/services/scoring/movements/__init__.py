from .cervical_rotation import CervicalRotationScorer
from .forward_lunge import ForwardLungeScorer
from .shoulder_reach import ShoulderReachBehindBackScorer
from .single_leg_dip import SingleLegDipScorer
from .trunk_rotation import TrunkRotationScorer


def get_movement_scorers():
    scorers = [
        CervicalRotationScorer(),
        TrunkRotationScorer(),
        ForwardLungeScorer(),
        SingleLegDipScorer(),
        ShoulderReachBehindBackScorer(),
    ]
    return {scorer.key: scorer for scorer in scorers}

