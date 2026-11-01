"""Unit tests for the transparent recommendation rules."""

from app.domain import models
from app.engine import recommendations
from app.engine import solvers
from app.samples import demo_data


def _solution(
    alternative_number: int,
    mean_skill_fit: float = 1.0,
    unmet_soft: int = 0,
    mean_rank: float = 1.0,
    unranked: int = 0,
) -> models.Solution:
    """Builds a solution holding only the indicators the rules read."""
    return models.Solution(
        id=f"sol-{alternative_number}",
        run_id="run-1",
        alternative_number=alternative_number,
        strategy_name="PREFERENCE",
        indicators={
            "efficiency": {
                "mean_skill_fit": mean_skill_fit,
                "unmet_soft_requirements_count": unmet_soft,
            },
            "fairness": {
                "mean_rank": mean_rank,
                "unranked_count": unranked,
                "worst_rank": 1,
                "rank_gini": 0.0,
                "rank_variance": 0.0,
            },
        },
    )


def test_priority_1_compares_unranked_count_before_mean_rank() -> None:
    """A better mean rank does not beat fewer students outside preferences."""
    recs = recommendations.generate_recommendations(
        [
            _solution(1, unranked=1, mean_rank=1.0),
            _solution(2, unranked=0, mean_rank=2.0),
        ]
    )

    assert recs[0].recommended_alternative_number == 2


def test_priority_2_breaks_full_tie_on_mean_rank() -> None:
    """With equal skill fit and unmet requirements, the better rank wins."""
    recs = recommendations.generate_recommendations(
        [_solution(2, mean_rank=1.2), _solution(3, mean_rank=1.1)]
    )

    assert recs[1].recommended_alternative_number == 3


def test_priority_2_compares_skill_fit_before_mean_rank() -> None:
    """Mean rank only breaks ties, so it cannot beat a higher skill fit."""
    recs = recommendations.generate_recommendations(
        [
            _solution(1, mean_skill_fit=0.9, mean_rank=1.0),
            _solution(2, mean_skill_fit=1.0, mean_rank=2.0),
        ]
    )

    assert recs[1].recommended_alternative_number == 2


def test_priority_2_compares_unmet_requirements_before_mean_rank() -> None:
    """Mean rank only breaks ties, so it cannot beat fewer unmet requirements."""
    recs = recommendations.generate_recommendations(
        [
            _solution(1, unmet_soft=1, mean_rank=1.0),
            _solution(2, unmet_soft=0, mean_rank=2.0),
        ]
    )

    assert recs[1].recommended_alternative_number == 2


def test_priority_2_on_demo_data_picks_best_ranked_of_the_tied() -> None:
    """On the demo run no tied alternative has a better mean rank."""
    benchmark = demo_data.get_standard_scenario()
    run = solvers.AssignmentEngine().run_assignment(
        students=benchmark["students"],
        projects=benchmark["projects"],
        skills=benchmark["skills"],
        max_alternatives=3,
    )

    picked_number = recommendations.generate_recommendations(run.solutions)[
        1
    ].recommended_alternative_number
    picked = run.solutions[picked_number - 1]

    def skill_keys(solution: models.Solution) -> tuple[float, int]:
        """Returns the two measures Priority 2 compares before mean rank."""
        efficiency = solution.indicators["efficiency"]
        return (
            efficiency["mean_skill_fit"],
            efficiency["unmet_soft_requirements_count"],
        )

    tied = [
        solution
        for solution in run.solutions
        if skill_keys(solution) == skill_keys(picked)
    ]
    assert len(tied) >= 2
    assert picked.indicators["fairness"]["mean_rank"] == min(
        solution.indicators["fairness"]["mean_rank"] for solution in tied
    )


def test_criteria_used_lists_the_real_sort_keys_in_order() -> None:
    """Each priority names exactly the measures it sorts on, in that order."""
    preference, skill, balanced = (
        rec.criteria_used
        for rec in recommendations.generate_recommendations([_solution(1)])
    )

    assert len(preference) == len(skill) == len(balanced) == 3
    assert "outside stated preferences" in preference[0]
    assert "Average student preference rank" in preference[1]
    assert "Worst individual student rank" in preference[2]
    assert "skill fit" in skill[0]
    assert "unmet soft skill requirements" in skill[1]
    assert "Average student preference rank" in skill[2]
    assert "Gini" in balanced[0]
    assert "variance" in balanced[1]
    assert "Average student preference rank" in balanced[2]
    assert not any("Harmonized" in criterion for criterion in balanced)
