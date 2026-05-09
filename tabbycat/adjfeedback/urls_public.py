from django.urls import path

from participants.models import Adjudicator, Team

from . import views
from .silent_round_views import SilentRoundFeedbackSubmitView, SilentRoundFeedbackTeamView

urlpatterns = [
    # Overviews
    path('progress/',
        views.PublicFeedbackProgress.as_view(),
        name='public_feedback_progress'),

    # Submission via Public Form
    path('add/',
        views.PublicAddFeedbackIndexView.as_view(),
        name='adjfeedback-public-add-index'),
    path('add/team/<int:source_id>/',
        views.PublicAddFeedbackByIdUrlView.as_view(model=Team),
        name='adjfeedback-public-add-from-team-pk'),
    path('add/adjudicator/<int:source_id>/',
        views.PublicAddFeedbackByIdUrlView.as_view(model=Adjudicator),
        name='adjfeedback-public-add-from-adjudicator-pk'),

    # Submission via Private URL
    path('add/t<slug:url_key>/',
        views.SpeakerAddFeedbackByRandomisedUrlView.as_view(),
        name='adjfeedback-public-add-from-team-randomised'),
    path('add/a<slug:url_key>/',
        views.AdjudicatorAddFeedbackByRandomisedUrlView.as_view(),
        name='adjfeedback-public-add-from-adjudicator-randomised'),

    # Silent round feedback — adj submits, teams view (both via private URL)
    path('silent/adj/<slug:url_key>/',
        SilentRoundFeedbackSubmitView.as_view(),
        name='adjfeedback-silent-round-feedback-submit'),
    path('silent/team/<slug:url_key>/',
        SilentRoundFeedbackTeamView.as_view(),
        name='adjfeedback-silent-round-feedback-team'),
]
