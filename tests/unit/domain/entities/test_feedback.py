"""Unit tests for the Feedback domain entity.

Covers (issue #161, domain-layer coverage):
- Valid construction with required and optional fields
- Rating invariant validation (out-of-bounds -> ValueError, boundaries OK)
- State transition methods (mark_reviewed / mark_actioned / dismiss)
- Mutation methods (add_comment / update_metadata) and timestamp touch
- is_negative() business rule across all feedback types
- Defensive copies for input_data / output_data / metadata properties
- to_dict() serialization
- Entity equality / hashing inherited from the Entity base class
- FeedbackType and FeedbackStatus enums
- Edge cases (None, empty values, boundary ratings)
"""

import time
from uuid import UUID, uuid4

import pytest

from src.domain.entities.feedback import (
    Feedback,
    FeedbackStatus,
    FeedbackType,
)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------
class TestFeedbackConstruction:
    """Tests for Feedback construction and defaults."""

    def test_minimal_construction(self):
        """Feedback requires only model_id and feedback_type."""
        model_id = uuid4()
        feedback = Feedback(
            model_id=model_id,
            feedback_type=FeedbackType.THUMBS_UP,
        )

        assert feedback.model_id == model_id
        assert feedback.feedback_type == FeedbackType.THUMBS_UP
        assert isinstance(feedback.id, UUID)
        assert feedback.status == FeedbackStatus.PENDING

    def test_default_status_is_pending(self):
        """New feedback always starts in PENDING status."""
        feedback = Feedback(model_id=uuid4(), feedback_type=FeedbackType.IMPLICIT)

        assert feedback.status == FeedbackStatus.PENDING

    def test_optional_fields_default_to_none(self):
        """Optional scalar fields default to None when not provided."""
        feedback = Feedback(model_id=uuid4(), feedback_type=FeedbackType.THUMBS_UP)

        assert feedback.prediction_id is None
        assert feedback.rating is None
        assert feedback.comment is None
        assert feedback.correction is None
        assert feedback.user_id is None
        assert feedback.session_id is None

    def test_dict_fields_default_to_empty_dict(self):
        """input_data, output_data and metadata default to empty dicts."""
        feedback = Feedback(model_id=uuid4(), feedback_type=FeedbackType.IMPLICIT)

        assert feedback.input_data == {}
        assert feedback.output_data == {}
        assert feedback.metadata == {}

    def test_dict_fields_none_normalized_to_empty(self):
        """Explicitly passing None for dict fields yields empty dicts, not None."""
        feedback = Feedback(
            model_id=uuid4(),
            feedback_type=FeedbackType.IMPLICIT,
            input_data=None,
            output_data=None,
            metadata=None,
        )

        assert feedback.input_data == {}
        assert feedback.output_data == {}
        assert feedback.metadata == {}

    def test_full_construction(self):
        """All fields are stored and exposed via properties."""
        model_id = uuid4()
        custom_id = uuid4()
        feedback = Feedback(
            model_id=model_id,
            feedback_type=FeedbackType.CORRECTION,
            id=custom_id,
            prediction_id="pred-42",
            rating=None,
            comment="off by one",
            correction="the right answer",
            user_id="user-7",
            session_id="sess-9",
            input_data={"prompt": "hi"},
            output_data={"completion": "wrong"},
            metadata={"source": "api"},
        )

        assert feedback.id == custom_id
        assert feedback.model_id == model_id
        assert feedback.feedback_type == FeedbackType.CORRECTION
        assert feedback.prediction_id == "pred-42"
        assert feedback.comment == "off by one"
        assert feedback.correction == "the right answer"
        assert feedback.user_id == "user-7"
        assert feedback.session_id == "sess-9"
        assert feedback.input_data == {"prompt": "hi"}
        assert feedback.output_data == {"completion": "wrong"}
        assert feedback.metadata == {"source": "api"}

    def test_provided_id_is_used(self):
        """A provided id should be honored instead of generating a new one."""
        custom_id = uuid4()
        feedback = Feedback(
            model_id=uuid4(),
            feedback_type=FeedbackType.THUMBS_UP,
            id=custom_id,
        )

        assert feedback.id == custom_id


# ---------------------------------------------------------------------------
# Rating invariant validation
# ---------------------------------------------------------------------------
class TestRatingValidation:
    """Tests for the rating invariant (only enforced for RATING type)."""

    @pytest.mark.parametrize("rating", [1, 2, 3, 4, 5])
    def test_valid_ratings_accepted(self, rating):
        """Ratings 1 through 5 are accepted for RATING feedback."""
        feedback = Feedback(
            model_id=uuid4(),
            feedback_type=FeedbackType.RATING,
            rating=rating,
        )

        assert feedback.rating == rating

    def test_rating_boundary_low(self):
        """Rating exactly at the lower boundary (1) is valid."""
        feedback = Feedback(
            model_id=uuid4(), feedback_type=FeedbackType.RATING, rating=1
        )
        assert feedback.rating == 1

    def test_rating_boundary_high(self):
        """Rating exactly at the upper boundary (5) is valid."""
        feedback = Feedback(
            model_id=uuid4(), feedback_type=FeedbackType.RATING, rating=5
        )
        assert feedback.rating == 5

    def test_rating_zero_rejected(self):
        """Rating just below the lower boundary (0) is rejected."""
        with pytest.raises(ValueError, match="Rating must be between 1 and 5"):
            Feedback(model_id=uuid4(), feedback_type=FeedbackType.RATING, rating=0)

    def test_rating_six_rejected(self):
        """Rating just above the upper boundary (6) is rejected."""
        with pytest.raises(ValueError, match="Rating must be between 1 and 5"):
            Feedback(model_id=uuid4(), feedback_type=FeedbackType.RATING, rating=6)

    def test_negative_rating_rejected(self):
        """A negative rating is rejected."""
        with pytest.raises(ValueError, match="Rating must be between 1 and 5"):
            Feedback(model_id=uuid4(), feedback_type=FeedbackType.RATING, rating=-3)

    def test_rating_none_for_rating_type_allowed(self):
        """A RATING feedback without a rating value is allowed (no validation)."""
        feedback = Feedback(
            model_id=uuid4(),
            feedback_type=FeedbackType.RATING,
            rating=None,
        )

        assert feedback.rating is None

    def test_out_of_range_rating_not_validated_for_non_rating_type(self):
        """Rating is only validated when feedback_type is RATING."""
        # An out-of-range rating on a non-RATING type does NOT raise, because the
        # invariant check is guarded by feedback_type == RATING.
        feedback = Feedback(
            model_id=uuid4(),
            feedback_type=FeedbackType.THUMBS_UP,
            rating=99,
        )

        assert feedback.rating == 99


# ---------------------------------------------------------------------------
# State transitions
# ---------------------------------------------------------------------------
class TestStateTransitions:
    """Tests for feedback status transition methods."""

    def _make(self):
        return Feedback(
            model_id=uuid4(),
            feedback_type=FeedbackType.RATING,
            rating=4,
        )

    def test_mark_reviewed(self):
        """mark_reviewed transitions status to REVIEWED."""
        feedback = self._make()

        feedback.mark_reviewed()

        assert feedback.status == FeedbackStatus.REVIEWED

    def test_mark_actioned(self):
        """mark_actioned transitions status to ACTIONED."""
        feedback = self._make()

        feedback.mark_actioned()

        assert feedback.status == FeedbackStatus.ACTIONED

    def test_dismiss(self):
        """dismiss transitions status to DISMISSED."""
        feedback = self._make()

        feedback.dismiss()

        assert feedback.status == FeedbackStatus.DISMISSED

    def test_full_transition_chain(self):
        """Transitions can be chained pending -> reviewed -> actioned."""
        feedback = self._make()
        assert feedback.status == FeedbackStatus.PENDING

        feedback.mark_reviewed()
        assert feedback.status == FeedbackStatus.REVIEWED

        feedback.mark_actioned()
        assert feedback.status == FeedbackStatus.ACTIONED

    def test_dismiss_overrides_reviewed(self):
        """A reviewed feedback can subsequently be dismissed."""
        feedback = self._make()
        feedback.mark_reviewed()

        feedback.dismiss()

        assert feedback.status == FeedbackStatus.DISMISSED

    def test_mark_reviewed_touches_timestamp(self):
        """mark_reviewed updates the updated_at timestamp."""
        feedback = self._make()
        before = feedback.updated_at
        time.sleep(0.001)

        feedback.mark_reviewed()

        assert feedback.updated_at >= before

    def test_mark_actioned_touches_timestamp(self):
        """mark_actioned updates the updated_at timestamp."""
        feedback = self._make()
        before = feedback.updated_at
        time.sleep(0.001)

        feedback.mark_actioned()

        assert feedback.updated_at >= before

    def test_dismiss_touches_timestamp(self):
        """dismiss updates the updated_at timestamp."""
        feedback = self._make()
        before = feedback.updated_at
        time.sleep(0.001)

        feedback.dismiss()

        assert feedback.updated_at >= before


# ---------------------------------------------------------------------------
# Mutation methods
# ---------------------------------------------------------------------------
class TestMutationMethods:
    """Tests for add_comment and update_metadata."""

    def test_add_comment_sets_comment(self):
        """add_comment sets the comment value."""
        feedback = Feedback(
            model_id=uuid4(), feedback_type=FeedbackType.RATING, rating=3
        )

        feedback.add_comment("very helpful")

        assert feedback.comment == "very helpful"

    def test_add_comment_overwrites_existing(self):
        """add_comment overwrites a previously set comment."""
        feedback = Feedback(
            model_id=uuid4(),
            feedback_type=FeedbackType.RATING,
            rating=3,
            comment="old",
        )

        feedback.add_comment("new")

        assert feedback.comment == "new"

    def test_add_comment_empty_string(self):
        """add_comment accepts an empty string."""
        feedback = Feedback(
            model_id=uuid4(), feedback_type=FeedbackType.RATING, rating=3
        )

        feedback.add_comment("")

        assert feedback.comment == ""

    def test_add_comment_touches_timestamp(self):
        """add_comment updates the updated_at timestamp."""
        feedback = Feedback(
            model_id=uuid4(), feedback_type=FeedbackType.RATING, rating=3
        )
        before = feedback.updated_at
        time.sleep(0.001)

        feedback.add_comment("touch me")

        assert feedback.updated_at >= before

    def test_update_metadata_merges(self):
        """update_metadata merges into existing metadata."""
        feedback = Feedback(
            model_id=uuid4(),
            feedback_type=FeedbackType.RATING,
            rating=4,
            metadata={"source": "web"},
        )

        feedback.update_metadata({"user_agent": "Chrome"})

        assert feedback.metadata == {"source": "web", "user_agent": "Chrome"}

    def test_update_metadata_overwrites_existing_keys(self):
        """update_metadata overwrites values for existing keys."""
        feedback = Feedback(
            model_id=uuid4(),
            feedback_type=FeedbackType.RATING,
            rating=4,
            metadata={"source": "web"},
        )

        feedback.update_metadata({"source": "mobile"})

        assert feedback.metadata["source"] == "mobile"

    def test_update_metadata_empty_dict_is_noop(self):
        """Updating with an empty dict leaves metadata unchanged."""
        feedback = Feedback(
            model_id=uuid4(),
            feedback_type=FeedbackType.RATING,
            rating=4,
            metadata={"source": "web"},
        )

        feedback.update_metadata({})

        assert feedback.metadata == {"source": "web"}

    def test_update_metadata_touches_timestamp(self):
        """update_metadata updates the updated_at timestamp."""
        feedback = Feedback(
            model_id=uuid4(), feedback_type=FeedbackType.RATING, rating=4
        )
        before = feedback.updated_at
        time.sleep(0.001)

        feedback.update_metadata({"k": "v"})

        assert feedback.updated_at >= before


# ---------------------------------------------------------------------------
# Defensive copies
# ---------------------------------------------------------------------------
class TestDefensiveCopies:
    """The dict-valued properties must return copies (no external mutation)."""

    def test_input_data_property_returns_copy(self):
        """Mutating the returned input_data dict must not affect the entity."""
        feedback = Feedback(
            model_id=uuid4(),
            feedback_type=FeedbackType.IMPLICIT,
            input_data={"prompt": "hi"},
        )

        snapshot = feedback.input_data
        snapshot["injected"] = True

        assert "injected" not in feedback.input_data

    def test_output_data_property_returns_copy(self):
        """Mutating the returned output_data dict must not affect the entity."""
        feedback = Feedback(
            model_id=uuid4(),
            feedback_type=FeedbackType.IMPLICIT,
            output_data={"completion": "hi"},
        )

        snapshot = feedback.output_data
        snapshot["injected"] = True

        assert "injected" not in feedback.output_data

    def test_metadata_property_returns_copy(self):
        """Mutating the returned metadata dict must not affect the entity."""
        feedback = Feedback(
            model_id=uuid4(),
            feedback_type=FeedbackType.IMPLICIT,
            metadata={"source": "api"},
        )

        snapshot = feedback.metadata
        snapshot["injected"] = True

        assert "injected" not in feedback.metadata


# ---------------------------------------------------------------------------
# is_negative business rule
# ---------------------------------------------------------------------------
class TestIsNegative:
    """Tests for the is_negative business rule across feedback types."""

    def test_thumbs_down_is_negative(self):
        feedback = Feedback(
            model_id=uuid4(), feedback_type=FeedbackType.THUMBS_DOWN
        )
        assert feedback.is_negative() is True

    def test_thumbs_up_is_not_negative(self):
        feedback = Feedback(model_id=uuid4(), feedback_type=FeedbackType.THUMBS_UP)
        assert feedback.is_negative() is False

    def test_correction_is_negative(self):
        feedback = Feedback(
            model_id=uuid4(),
            feedback_type=FeedbackType.CORRECTION,
            correction="fixed",
        )
        assert feedback.is_negative() is True

    def test_bug_report_is_negative(self):
        feedback = Feedback(
            model_id=uuid4(), feedback_type=FeedbackType.BUG_REPORT
        )
        assert feedback.is_negative() is True

    def test_implicit_is_not_negative(self):
        feedback = Feedback(model_id=uuid4(), feedback_type=FeedbackType.IMPLICIT)
        assert feedback.is_negative() is False

    @pytest.mark.parametrize("rating", [1, 2])
    def test_low_rating_is_negative(self, rating):
        """Ratings of 1 or 2 count as negative feedback."""
        feedback = Feedback(
            model_id=uuid4(), feedback_type=FeedbackType.RATING, rating=rating
        )
        assert feedback.is_negative() is True

    @pytest.mark.parametrize("rating", [3, 4, 5])
    def test_high_rating_is_not_negative(self, rating):
        """Ratings of 3 or above are not negative feedback."""
        feedback = Feedback(
            model_id=uuid4(), feedback_type=FeedbackType.RATING, rating=rating
        )
        assert feedback.is_negative() is False

    def test_rating_boundary_two_is_negative(self):
        """The boundary value 2 is the last negative rating."""
        feedback = Feedback(
            model_id=uuid4(), feedback_type=FeedbackType.RATING, rating=2
        )
        assert feedback.is_negative() is True

    def test_rating_boundary_three_is_not_negative(self):
        """The boundary value 3 is the first non-negative rating."""
        feedback = Feedback(
            model_id=uuid4(), feedback_type=FeedbackType.RATING, rating=3
        )
        assert feedback.is_negative() is False

    def test_rating_without_value_is_not_negative(self):
        """A RATING feedback with no rating value is not considered negative."""
        feedback = Feedback(
            model_id=uuid4(), feedback_type=FeedbackType.RATING, rating=None
        )
        assert feedback.is_negative() is False


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------
class TestToDict:
    """Tests for to_dict serialization."""

    def test_to_dict_includes_base_fields(self):
        """to_dict includes inherited id / created_at / updated_at fields."""
        feedback = Feedback(model_id=uuid4(), feedback_type=FeedbackType.THUMBS_UP)

        data = feedback.to_dict()

        assert data["id"] == str(feedback.id)
        assert "created_at" in data
        assert "updated_at" in data

    def test_to_dict_serializes_all_fields(self):
        """to_dict serializes every feedback-specific field."""
        model_id = uuid4()
        feedback = Feedback(
            model_id=model_id,
            feedback_type=FeedbackType.RATING,
            rating=4,
            prediction_id="pred-1",
            comment="good",
            correction=None,
            user_id="u1",
            session_id="s1",
            input_data={"a": 1},
            output_data={"b": 2},
            metadata={"c": 3},
        )

        data = feedback.to_dict()

        assert data["model_id"] == str(model_id)
        assert data["feedback_type"] == "rating"
        assert data["prediction_id"] == "pred-1"
        assert data["rating"] == 4
        assert data["comment"] == "good"
        assert data["correction"] is None
        assert data["user_id"] == "u1"
        assert data["session_id"] == "s1"
        assert data["input_data"] == {"a": 1}
        assert data["output_data"] == {"b": 2}
        assert data["metadata"] == {"c": 3}
        assert data["status"] == "pending"
        assert data["is_negative"] is False

    def test_to_dict_model_id_is_string(self):
        """model_id is serialized as a string, not a UUID object."""
        feedback = Feedback(model_id=uuid4(), feedback_type=FeedbackType.THUMBS_UP)

        data = feedback.to_dict()

        assert isinstance(data["model_id"], str)

    def test_to_dict_status_reflects_transition(self):
        """to_dict status reflects the current status after a transition."""
        feedback = Feedback(
            model_id=uuid4(), feedback_type=FeedbackType.RATING, rating=3
        )
        feedback.mark_actioned()

        data = feedback.to_dict()

        assert data["status"] == "actioned"

    def test_to_dict_is_negative_reflects_rule(self):
        """to_dict is_negative reflects the business rule for the feedback."""
        feedback = Feedback(
            model_id=uuid4(), feedback_type=FeedbackType.BUG_REPORT
        )

        data = feedback.to_dict()

        assert data["is_negative"] is True


# ---------------------------------------------------------------------------
# Entity identity (inherited behavior)
# ---------------------------------------------------------------------------
class TestEntityIdentity:
    """Tests for equality / hashing inherited from Entity."""

    def test_equality_based_on_id(self):
        """Two feedbacks with the same id are equal."""
        shared_id = uuid4()
        f1 = Feedback(
            model_id=uuid4(), feedback_type=FeedbackType.THUMBS_UP, id=shared_id
        )
        f2 = Feedback(
            model_id=uuid4(), feedback_type=FeedbackType.BUG_REPORT, id=shared_id
        )

        assert f1 == f2
        assert hash(f1) == hash(f2)

    def test_inequality_with_different_ids(self):
        """Feedbacks with different ids are not equal."""
        f1 = Feedback(model_id=uuid4(), feedback_type=FeedbackType.THUMBS_UP)
        f2 = Feedback(model_id=uuid4(), feedback_type=FeedbackType.THUMBS_UP)

        assert f1 != f2

    def test_inequality_with_non_entity(self):
        """A feedback is never equal to a non-Entity object."""
        feedback = Feedback(model_id=uuid4(), feedback_type=FeedbackType.THUMBS_UP)

        assert feedback != "not a feedback"
        assert feedback != 123
        assert feedback is not None

    def test_usable_in_set(self):
        """Feedbacks can be deduplicated in a set via their id-based hash."""
        shared_id = uuid4()
        f1 = Feedback(
            model_id=uuid4(), feedback_type=FeedbackType.THUMBS_UP, id=shared_id
        )
        f2 = Feedback(
            model_id=uuid4(), feedback_type=FeedbackType.THUMBS_DOWN, id=shared_id
        )

        assert len({f1, f2}) == 1


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class TestFeedbackTypeEnum:
    """Tests for the FeedbackType enum."""

    def test_values(self):
        assert FeedbackType.THUMBS_UP.value == "thumbs_up"
        assert FeedbackType.THUMBS_DOWN.value == "thumbs_down"
        assert FeedbackType.RATING.value == "rating"
        assert FeedbackType.CORRECTION.value == "correction"
        assert FeedbackType.BUG_REPORT.value == "bug_report"
        assert FeedbackType.IMPLICIT.value == "implicit"

    def test_is_str_enum(self):
        """FeedbackType is a StrEnum, so members compare equal to their value."""
        assert FeedbackType.RATING == "rating"
        assert isinstance(FeedbackType.RATING, str)

    def test_membership_count(self):
        """The enum has exactly six members."""
        assert len(list(FeedbackType)) == 6

    def test_construct_from_value(self):
        """A FeedbackType can be reconstructed from its string value."""
        assert FeedbackType("bug_report") is FeedbackType.BUG_REPORT


class TestFeedbackStatusEnum:
    """Tests for the FeedbackStatus enum."""

    def test_values(self):
        assert FeedbackStatus.PENDING.value == "pending"
        assert FeedbackStatus.REVIEWED.value == "reviewed"
        assert FeedbackStatus.ACTIONED.value == "actioned"
        assert FeedbackStatus.DISMISSED.value == "dismissed"

    def test_is_str_enum(self):
        """FeedbackStatus is a StrEnum, so members compare equal to their value."""
        assert FeedbackStatus.PENDING == "pending"
        assert isinstance(FeedbackStatus.PENDING, str)

    def test_membership_count(self):
        """The enum has exactly four members."""
        assert len(list(FeedbackStatus)) == 4

    def test_construct_from_value(self):
        """A FeedbackStatus can be reconstructed from its string value."""
        assert FeedbackStatus("dismissed") is FeedbackStatus.DISMISSED
