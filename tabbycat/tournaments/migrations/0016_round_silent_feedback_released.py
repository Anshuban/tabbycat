from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tournaments', '0015_alter_round_draw_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='round',
            name='silent_feedback_released',
            field=models.BooleanField(
                default=False,
                verbose_name='silent round feedback released',
                help_text='If set, teams can view the adjudicator\'s written feedback for this silent round via their private URL.',
            ),
        ),
    ]
