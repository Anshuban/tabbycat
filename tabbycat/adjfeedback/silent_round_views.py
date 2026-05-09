"""Views for silent round feedback.

Each adjudicator submits their own independent feedback per debate.
Feedback is private — other adjudicators in the same panel cannot see
each other's write-ups. Only the submitting adj, the teams in that debate,
and the tab/CA can see a given piece of feedback.

Teams only see feedback after the tab enables release via the
'silent_round_feedback_released' preference in Tab Release settings.

The entire feature can be disabled per-tournament via the
'silent_round_feedback_enabled' preference.
"""
import logging

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext as _
from django.views.generic import TemplateView

from adjallocation.models import DebateAdjudicator
from draw.models import Debate
from participants.models import Person
from tournaments.mixins import TournamentMixin
from utils.mixins import AdministratorMixin

from .models import SilentRoundFeedback

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Adjudicator: submit silent round feedback via private URL
# ---------------------------------------------------------------------------

class SilentRoundFeedbackSubmitView(TournamentMixin, TemplateView):
    """Shown to an adjudicator via their private URL.

    Lists all silent-round debates they adjudicated (where draw + motions
    are both released), allowing them to submit or update their own write-up
    for each. Each adjudicator sees only their own submission.
    """
    template_name = 'silent_round_feedback_submit.html'

    def _get_adjudicator(self):
        person = get_object_or_404(Person, url_key=self.kwargs['url_key'])
        if not hasattr(person, 'adjudicator'):
            raise PermissionDenied(_("This page is only available to adjudicators."))
        return person.adjudicator

    def _feature_enabled(self):
        return self.tournament.pref('silent_round_feedback_enabled')

    def get_context_data(self, **kwargs):
        adjudicator = self._get_adjudicator()
        tournament = self.tournament

        if not self._feature_enabled():
            kwargs['feature_disabled'] = True
            kwargs['adjudicator'] = adjudicator
            return super().get_context_data(**kwargs)

        from tournaments.models import Round
        debateadjs = DebateAdjudicator.objects.filter(
            adjudicator=adjudicator,
            debate__round__tournament=tournament,
            debate__round__silent=True,
            debate__round__draw_status=Round.Status.RELEASED,
            debate__round__motions_status=Round.MotionsStatus.MOTIONS_RELEASED,
        ).select_related(
            'debate__round',
        ).prefetch_related(
            'debate__debateteam_set__team',
        ).order_by('debate__round__seq')

        # Each adj sees only their own submission
        entries = []
        for da in debateadjs:
            try:
                existing = SilentRoundFeedback.objects.get(debate=da.debate, submitted_by=da)
            except SilentRoundFeedback.DoesNotExist:
                existing = None
            entries.append({
                'debateadj': da,
                'debate': da.debate,
                'existing': existing,
            })

        kwargs['adjudicator'] = adjudicator
        kwargs['entries'] = entries
        kwargs['url_key'] = self.kwargs['url_key']
        return super().get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        adjudicator = self._get_adjudicator()
        tournament = self.tournament

        if not self._feature_enabled():
            raise PermissionDenied(_("Silent round feedback is not enabled for this tournament."))

        debate_id = request.POST.get('debate_id')
        feedback_text = request.POST.get('feedback_text', '').strip()

        if not debate_id or not feedback_text:
            messages.error(request, _("Please provide feedback text before submitting."))
            return redirect(request.path)

        from tournaments.models import Round
        debate = get_object_or_404(
            Debate,
            id=debate_id,
            round__tournament=tournament,
            round__silent=True,
            round__draw_status=Round.Status.RELEASED,
            round__motions_status=Round.MotionsStatus.MOTIONS_RELEASED,
        )

        try:
            debateadj = DebateAdjudicator.objects.get(adjudicator=adjudicator, debate=debate)
        except DebateAdjudicator.DoesNotExist:
            raise PermissionDenied(_("You were not an adjudicator in this debate."))

        obj, created = SilentRoundFeedback.objects.update_or_create(
            debate=debate,
            submitted_by=debateadj,
            defaults={'feedback_text': feedback_text},
        )

        if created:
            messages.success(request, _("Feedback submitted successfully."))
        else:
            messages.success(request, _("Feedback updated successfully."))

        logger.info("Silent round feedback %s by %s for debate %s",
                    'created' if created else 'updated',
                    adjudicator.name, debate)

        return redirect(request.path)


# ---------------------------------------------------------------------------
# Teams: view silent round feedback via private URL
# ---------------------------------------------------------------------------

class SilentRoundFeedbackTeamView(TournamentMixin, TemplateView):
    """Shown to a team member via their private URL.

    Only visible after the tab sets silent_round_feedback_released = True
    in the Tab Release preferences. Teams see all adjudicators' feedback
    for their silent round debates (each adj's write-up shown separately).
    """
    template_name = 'silent_round_feedback_team_view.html'

    def get_context_data(self, **kwargs):
        person = get_object_or_404(Person, url_key=self.kwargs['url_key'])
        tournament = self.tournament

        if not hasattr(person, 'speaker'):
            raise PermissionDenied(_("This page is only available to team members."))

        team = person.speaker.team
        enabled = tournament.pref('silent_round_feedback_enabled')
        released = tournament.pref('silent_round_feedback_released')

        kwargs['person'] = person
        kwargs['team'] = team
        kwargs['feature_disabled'] = not enabled
        kwargs['not_released'] = not released

        if not enabled or not released:
            return super().get_context_data(**kwargs)

        from draw.models import DebateTeam
        from tournaments.models import Round
        debateteams = DebateTeam.objects.filter(
            team=team,
            debate__round__tournament=tournament,
            debate__round__silent=True,
            debate__round__draw_status=Round.Status.RELEASED,
            debate__round__motions_status=Round.MotionsStatus.MOTIONS_RELEASED,
        ).select_related(
            'debate__round',
        ).prefetch_related(
            'debate__debateteam_set__team',
            'debate__debateadjudicator_set__adjudicator',
            'debate__silent_round_feedbacks__submitted_by__adjudicator',
        ).order_by('debate__round__seq')

        entries = []
        for dt in debateteams:
            feedbacks = list(dt.debate.silent_round_feedbacks.all())
            entries.append({
                'debate': dt.debate,
                'feedbacks': feedbacks,   # one per adj who submitted
            })

        kwargs['entries'] = entries
        return super().get_context_data(**kwargs)


# ---------------------------------------------------------------------------
# Tab/CA: view all silent round feedback for the tournament
# ---------------------------------------------------------------------------

class SilentRoundFeedbackAdminView(AdministratorMixin, TournamentMixin, TemplateView):
    """Admin view of all submitted silent round feedback.

    Shows each adjudicator's submission separately. Tab and CA can see
    all submissions regardless of release status.
    Also shows which debates have partial or no submissions yet.
    """
    template_name = 'silent_round_feedback_admin.html'

    def get_context_data(self, **kwargs):
        tournament = self.tournament
        enabled = tournament.pref('silent_round_feedback_enabled')
        released = tournament.pref('silent_round_feedback_released')

        from tournaments.models import Round
        # All silent rounds with draw+motions released
        silent_debates = Debate.objects.filter(
            round__tournament=tournament,
            round__silent=True,
            round__draw_status=Round.Status.RELEASED,
            round__motions_status=Round.MotionsStatus.MOTIONS_RELEASED,
        ).select_related('round').prefetch_related(
            'debateadjudicator_set__adjudicator',
            'debateteam_set__team',
            'silent_round_feedbacks__submitted_by__adjudicator',
        ).order_by('round__seq', 'room_rank')

        debate_entries = []
        for debate in silent_debates:
            all_adjs = list(debate.debateadjudicator_set.all())
            submitted = {fb.submitted_by_id: fb for fb in debate.silent_round_feedbacks.all()}
            adj_entries = []
            for da in all_adjs:
                adj_entries.append({
                    'debateadj': da,
                    'feedback': submitted.get(da.id),
                })
            debate_entries.append({
                'debate': debate,
                'adj_entries': adj_entries,
                'submitted_count': len(submitted),
                'total_adjs': len(all_adjs),
            })

        kwargs['debate_entries'] = debate_entries
        kwargs['enabled'] = enabled
        kwargs['released'] = released
        kwargs['page_title'] = _("Silent Round Feedback")
        kwargs['page_emoji'] = "📝"
        return super().get_context_data(**kwargs)
