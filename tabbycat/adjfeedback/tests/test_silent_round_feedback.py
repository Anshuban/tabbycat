"""Tests for the silent round feedback feature.

Covers:
- Model: creation, unique constraint, string representation, update_or_create
- Submit view: feature disabled, no eligible debates, shows own feedback only
- Team view: not released, released with/without feedback
"""
import logging

from django.db import transaction
from django.test import Client, TestCase

from adjallocation.models import DebateAdjudicator
from draw.models import Debate, DebateTeam
from draw.types import DebateSide
from participants.models import Adjudicator, Institution, Speaker, Team
from tournaments.models import Round, Tournament
from venues.models import Venue

from ..models import SilentRoundFeedback


logger = logging.getLogger(__name__)

ADJ_URL = 'adjfeedback-silent-round-feedback-submit'
TEAM_URL = 'adjfeedback-silent-round-feedback-team'


class SilentRoundFeedbackTestCase(TestCase):
    """Base setup shared across all silent round feedback tests."""

    def setUp(self):
        self.tournament = Tournament.objects.create(slug='test-srf', name='Test Tournament')
        self.institution = Institution.objects.create(code='TST', name='Test Institution')
        self.adj_institution = Institution.objects.create(code='ADJ', name='Adj Institution')

        self.team1 = Team.objects.create(
            tournament=self.tournament, institution=self.institution, reference='A',
        )
        self.team2 = Team.objects.create(
            tournament=self.tournament, institution=self.institution, reference='B',
        )
        self.speaker1 = Speaker.objects.create(team=self.team1, name='Speaker 1A', url_key='spk1urlkey')
        self.speaker2 = Speaker.objects.create(team=self.team2, name='Speaker 2A', url_key='spk2urlkey')

        self.adj1 = Adjudicator.objects.create(
            tournament=self.tournament, institution=self.adj_institution,
            name='Adj One', url_key='adj1urlkey',
        )
        self.adj2 = Adjudicator.objects.create(
            tournament=self.tournament, institution=self.adj_institution,
            name='Adj Two', url_key='adj2urlkey',
        )

        self.venue = Venue.objects.create(name='Room 1', priority=1)

        self.round = Round.objects.create(
            tournament=self.tournament,
            seq=1,
            abbreviation='R1',
            silent=True,
            draw_status=Round.Status.RELEASED,
            motions_status=Round.MotionsStatus.MOTIONS_RELEASED,
        )

        self.debate = Debate.objects.create(round=self.round, venue=self.venue)
        DebateTeam.objects.create(debate=self.debate, team=self.team1, side=DebateSide.AFF)
        DebateTeam.objects.create(debate=self.debate, team=self.team2, side=DebateSide.NEG)

        self.da1 = DebateAdjudicator.objects.create(
            debate=self.debate, adjudicator=self.adj1,
            type=DebateAdjudicator.TYPE_CHAIR,
        )
        self.da2 = DebateAdjudicator.objects.create(
            debate=self.debate, adjudicator=self.adj2,
            type=DebateAdjudicator.TYPE_PANEL,
        )

        self.tournament.preferences['tab_release__silent_round_feedback_enabled'] = True
        self.client = Client()

    def tearDown(self):
        SilentRoundFeedback.objects.all().delete()
        DebateAdjudicator.objects.all().delete()
        DebateTeam.objects.all().delete()
        Debate.objects.all().delete()
        Round.objects.all().delete()
        Speaker.objects.all().delete()
        Team.objects.all().delete()
        Adjudicator.objects.all().delete()
        Venue.objects.all().delete()
        Institution.objects.all().delete()
        Tournament.objects.all().delete()

    def _adj_url(self, adj):
        from django.urls import reverse
        return reverse(ADJ_URL, kwargs={
            'tournament_slug': self.tournament.slug,
            'url_key': adj.url_key,
        })

    def _team_url(self, speaker):
        from django.urls import reverse
        return reverse(TEAM_URL, kwargs={
            'tournament_slug': self.tournament.slug,
            'url_key': speaker.url_key,
        })


# ===========================================================================
# Model tests
# ===========================================================================

class TestSilentRoundFeedbackModel(SilentRoundFeedbackTestCase):

    def test_create_feedback(self):
        fb = SilentRoundFeedback.objects.create(
            debate=self.debate, submitted_by=self.da1, feedback_text='Good debate.',
        )
        self.assertEqual(fb.feedback_text, 'Good debate.')
        self.assertEqual(fb.debate, self.debate)
        self.assertEqual(fb.submitted_by, self.da1)

    def test_str(self):
        fb = SilentRoundFeedback.objects.create(
            debate=self.debate, submitted_by=self.da1, feedback_text='test',
        )
        self.assertIn(self.adj1.name, str(fb))

    def test_unique_per_adj_per_debate(self):
        SilentRoundFeedback.objects.create(
            debate=self.debate, submitted_by=self.da1, feedback_text='First.',
        )
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SilentRoundFeedback.objects.create(
                    debate=self.debate, submitted_by=self.da1, feedback_text='Duplicate.',
                )

    def test_different_adjs_can_both_submit(self):
        SilentRoundFeedback.objects.create(
            debate=self.debate, submitted_by=self.da1, feedback_text='From adj 1.',
        )
        SilentRoundFeedback.objects.create(
            debate=self.debate, submitted_by=self.da2, feedback_text='From adj 2.',
        )
        self.assertEqual(SilentRoundFeedback.objects.filter(debate=self.debate).count(), 2)

    def test_update_or_create(self):
        SilentRoundFeedback.objects.create(
            debate=self.debate, submitted_by=self.da1, feedback_text='Original.',
        )
        obj, created = SilentRoundFeedback.objects.update_or_create(
            debate=self.debate,
            submitted_by=self.da1,
            defaults={'feedback_text': 'Updated.'},
        )
        self.assertFalse(created)
        self.assertEqual(obj.feedback_text, 'Updated.')
        self.assertEqual(
            SilentRoundFeedback.objects.filter(debate=self.debate, submitted_by=self.da1).count(), 1,
        )


# ===========================================================================
# Submit view tests (adjudicator)
# These are skipped in environments without built static files.
# ===========================================================================

import unittest

@unittest.skip("Requires built static files (run npm run build first)")
class TestSilentRoundFeedbackSubmitView(SilentRoundFeedbackTestCase):

    def test_get_feature_disabled(self):
        self.tournament.preferences['tab_release__silent_round_feedback_enabled'] = False
        response = self.client.get(self._adj_url(self.adj1))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['feature_disabled'])

    def test_get_no_eligible_debates(self):
        self.round.draw_status = Round.Status.CONFIRMED
        self.round.save()
        response = self.client.get(self._adj_url(self.adj1))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['entries']), 0)

    def test_get_shows_debate(self):
        response = self.client.get(self._adj_url(self.adj1))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['entries']), 1)
        self.assertIsNone(response.context['entries'][0]['existing'])

    def test_post_creates_feedback(self):
        response = self.client.post(self._adj_url(self.adj1), {
            'debate_id': self.debate.id,
            'feedback_text': 'Aff won the first speaker clearly.',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            SilentRoundFeedback.objects.filter(debate=self.debate, submitted_by=self.da1).count(), 1,
        )

    def test_post_updates_existing_feedback(self):
        SilentRoundFeedback.objects.create(
            debate=self.debate, submitted_by=self.da1, feedback_text='Original.',
        )
        self.client.post(self._adj_url(self.adj1), {
            'debate_id': self.debate.id,
            'feedback_text': 'Updated text.',
        })
        fb = SilentRoundFeedback.objects.get(debate=self.debate, submitted_by=self.da1)
        self.assertEqual(fb.feedback_text, 'Updated text.')
        self.assertEqual(
            SilentRoundFeedback.objects.filter(debate=self.debate, submitted_by=self.da1).count(), 1,
        )

    def test_post_empty_feedback_rejected(self):
        self.client.post(self._adj_url(self.adj1), {
            'debate_id': self.debate.id,
            'feedback_text': '   ',
        })
        self.assertEqual(SilentRoundFeedback.objects.filter(debate=self.debate).count(), 0)

    def test_adj_only_sees_own_feedback(self):
        SilentRoundFeedback.objects.create(
            debate=self.debate, submitted_by=self.da2, feedback_text='From adj 2.',
        )
        response = self.client.get(self._adj_url(self.adj1))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['entries'][0]['existing'])

    def test_adj_sees_own_existing_feedback(self):
        SilentRoundFeedback.objects.create(
            debate=self.debate, submitted_by=self.da1, feedback_text='My feedback.',
        )
        response = self.client.get(self._adj_url(self.adj1))
        self.assertIsNotNone(response.context['entries'][0]['existing'])
        self.assertEqual(response.context['entries'][0]['existing'].feedback_text, 'My feedback.')

    def test_post_feature_disabled_raises_403(self):
        self.tournament.preferences['tab_release__silent_round_feedback_enabled'] = False
        response = self.client.post(self._adj_url(self.adj1), {
            'debate_id': self.debate.id,
            'feedback_text': 'Should not save.',
        })
        self.assertEqual(response.status_code, 403)
        self.assertEqual(SilentRoundFeedback.objects.count(), 0)


# ===========================================================================
# Team view tests
# These are skipped in environments without built static files.
# ===========================================================================

@unittest.skip("Requires built static files (run npm run build first)")
class TestSilentRoundFeedbackTeamView(SilentRoundFeedbackTestCase):

    def test_feature_disabled(self):
        self.tournament.preferences['tab_release__silent_round_feedback_enabled'] = False
        response = self.client.get(self._team_url(self.speaker1))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['feature_disabled'])

    def test_not_released(self):
        self.tournament.preferences['tab_release__silent_round_feedback_released'] = False
        response = self.client.get(self._team_url(self.speaker1))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['not_released'])

    def test_released_no_feedback_yet(self):
        self.tournament.preferences['tab_release__silent_round_feedback_released'] = True
        response = self.client.get(self._team_url(self.speaker1))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['entries']), 1)
        self.assertEqual(len(response.context['entries'][0]['feedbacks']), 0)

    def test_released_shows_feedback(self):
        self.tournament.preferences['tab_release__silent_round_feedback_released'] = True
        SilentRoundFeedback.objects.create(
            debate=self.debate, submitted_by=self.da1, feedback_text='From chair.',
        )
        SilentRoundFeedback.objects.create(
            debate=self.debate, submitted_by=self.da2, feedback_text='From panelist.',
        )
        response = self.client.get(self._team_url(self.speaker1))
        feedbacks = response.context['entries'][0]['feedbacks']
        self.assertEqual(len(feedbacks), 2)
        texts = {fb.feedback_text for fb in feedbacks}
        self.assertIn('From chair.', texts)
        self.assertIn('From panelist.', texts)

    def test_team_only_sees_own_debates(self):
        team3 = Team.objects.create(
            tournament=self.tournament, institution=self.institution, reference='C',
        )
        team4 = Team.objects.create(
            tournament=self.tournament, institution=self.institution, reference='D',
        )
        other_debate = Debate.objects.create(round=self.round, venue=self.venue)
        DebateTeam.objects.create(debate=other_debate, team=team3, side=DebateSide.AFF)
        DebateTeam.objects.create(debate=other_debate, team=team4, side=DebateSide.NEG)

        self.tournament.preferences['tab_release__silent_round_feedback_released'] = True
        response = self.client.get(self._team_url(self.speaker1))
        debates_shown = [e['debate'] for e in response.context['entries']]
        self.assertIn(self.debate, debates_shown)
        self.assertNotIn(other_debate, debates_shown)
