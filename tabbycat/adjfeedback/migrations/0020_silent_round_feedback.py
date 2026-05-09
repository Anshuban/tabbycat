from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('adjfeedback', '0019_merge_20241106_0903'),
        ('adjallocation', '0001_initial'),
        ('draw', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SilentRoundFeedback',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('feedback_text', models.TextField(
                    verbose_name='feedback',
                    help_text='Written feedback for all teams in this debate. Only visible to teams after the tab releases it.',
                )),
                ('submitted_at', models.DateTimeField(auto_now_add=True, verbose_name='submitted at')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='last updated')),
                ('debate', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='silent_round_feedbacks',
                    to='draw.debate',
                    verbose_name='debate',
                )),
                ('submitted_by', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='adjallocation.debateadjudicator',
                    verbose_name='submitted by (debate adjudicator)',
                    related_name='silent_round_feedbacks',
                )),
            ],
            options={
                'verbose_name': 'silent round feedback',
                'verbose_name_plural': 'silent round feedbacks',
            },
        ),
        migrations.AddConstraint(
            model_name='silentroundfeedback',
            constraint=models.UniqueConstraint(
                fields=['debate', 'submitted_by'],
                name='unique_silent_feedback_per_adj_per_debate',
            ),
        ),
    ]
