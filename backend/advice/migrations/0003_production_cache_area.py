"""Key the PVGIS cache on the postcode century it actually resolves.

`postcode4_to_latlon` looks up `postcode4[:2]`, so every postcode in one
century got a byte-identical series while the cache kept a separate 60 kB row
for each of them, forever.

Dropped and recreated rather than renamed and shrunk. The rows that exist hold
a four character value in a column that becomes two characters wide, and more
to the point they are keyed by something that no longer means what it meant:
under the new key they would collide with each other. Losing them costs one
external call per century and orientation that is asked for again, which is
what a cache is for.
"""

from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("advice", "0002_cache_table")]

    operations = [
        migrations.DeleteModel(name="ProductionCache"),
        migrations.CreateModel(
            name="ProductionCache",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("postcode_area", models.CharField(max_length=2)),
                ("azimuth_deg", models.SmallIntegerField()),
                ("tilt_deg", models.SmallIntegerField()),
                ("weather_year", models.SmallIntegerField()),
                ("production_w_per_kwp", models.BinaryField()),
                ("temperature_c", models.BinaryField()),
                ("source", models.CharField(max_length=16)),
                ("fetched_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("postcode_area", "azimuth_deg", "tilt_deg", "weather_year"),
                        name="unique_production_cache_key",
                    )
                ],
            },
        ),
    ]
