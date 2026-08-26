# Double counting: what the two repairs are worth

`docs/decisions.md`, under "What was not decided here", records that round one
asks "Verbruik per jaar", round two asks whether the household has a car or a
heat pump, and the model adds those on top of the round one answer. A visitor
who charges at home reads the total off their annual bill, the car is already
in it, and the model counts it twice.

Two repairs are named there and they are different products. This file puts
numbers under the choice between them. It decides nothing: what a visitor is
asked and what they are told is Stijn's call, and the point of this sheet is to
make that call takeable in one sitting.

## Read this before the numbers

The filename carries the date the question was raised on this branch. Every
figure below was measured on 2026-08-26 by driving the real engine.

Everything was measured three times, and none of the repeats was a formality.
The first pass reproduced `docs/decisions.md` to the euro: 456 against 634 for
the reference household with a car at night, 291 against 479 with a heat pump,
97 against 212 with a car on its own surplus. That is the evidence that this
harness is the same calculation the decision was recorded from.

Concurrent work on this branch then replaced the offline production fallback
twice. The fixed twelve hour half sine first became an energy weighted window of
13.28 hours, which is what the second pass measured; that window was then
withdrawn before it landed, in favour of the same twelve hour shape centred on
solar noon, which is decision 17 in `docs/decisions.md`. `ORIENTATION_FACTORS`
was remeasured in the same round and is decision 16. The second pass therefore
describes a model that never shipped, and its figures have been replaced rather
than kept.

The tables below are the third pass, against the code that ships:
`ampeer_sim/production/pvgis.py` at sha256 `7b837b6bbe07cd85...` and
`ampeer_sim/production/fallback_yield.py` at `9d54ef6db8b8765e...`,
in which 3.5 kWp facing south at 35 degrees yields 3674.0 kWh a year after
losses and the reference household's shock is 623.50 where it was 633.73 before
that work and 585.72 under the withdrawn window.

Three passes on three materially different production models is more evidence
about this document than any one of them is. Every euro figure moved every time,
and every structural conclusion held every time: repair 1 and repair 2 stayed
identical to the cent, the same three of six bands stayed non-overlapping, the
carve-out floor stayed at 2550 kWh, and the kilometre crossing stayed between
6200 and 6400. The euro columns are worth what a model revision leaves them
worth. The conclusions are worth more.

What did not move between the two passes is the whole of the argument: repair 1
and repair 2 stayed identical to the cent, the carve-out floor stayed at 2550
kWh, the break-even stayed between 6200 and 6400 kilometres a year, and the
same three households lost the same advice. So read the euro columns as a scale
and the structure as the finding.

## The three readings

Write T for the number on the visitor's annual bill, which already contains the
asset, and A for the electricity the model attributes to that asset.

| reading | what the visitor types | what the model composes | modelled total |
|---|---|---|---|
| today | T | base = T, then add A | T + A |
| repair 1 | T - A | base = T - A, then add A | T |
| repair 2 | T | base = T - A, then add A | T |

Repair 1 is "say at the question which figure is wanted". Repair 2 is "read the
answer as the total and carve the modelled asset out of it".

Repair 2 was run as its own code path rather than assumed equal to repair 1: it
starts from T, computes A from the asset models alone the way a real carve-out
would have to, since it cannot look at the base, subtracts, and runs. That is
not pedantry. It is the only way to find out whether A is recoverable without
knowing the base, and it is.

## What each household is told

Six golden households from `tests/golden/households.json` plus the reference
household of chapter 17 of `docs/methodologie.md` in the three asset shapes
`docs/decisions.md` quotes. Flat consumption profile, offline production
fallback, weather year 2025, profile year 2025, 2027 mid tariffs on a fixed
contract. Euro per year, the cost of the end of net metering. The last column is
the same gap read the other way round: what a household would see its figure do
if either repair shipped.

| household | base kWh | asset kWh | bill total kWh | today | repair 1 | repair 2 | gap of today | gap of today | rise if repaired |
|---|---|---|---|---|---|---|---|---|---|
| hand_checkable | 3650 | 0 | 3650.0 | 16.46 | 16.46 | 16.46 | 0.00 | 0.0% | 0.0% |
| large_array_small_use | 2200 | 0 | 2200.0 | 1666.13 | 1666.13 | 1666.13 | 0.00 | 0.0% | 0.0% |
| rob_fixed_contract | 3500 | 0 | 3500.0 | 623.50 | 623.50 | 623.50 | 0.00 | 0.0% | 0.0% |
| marloes_ev_at_night | 3000 | 2700.0 | 5700.0 | 557.74 | 795.03 | 795.03 | -237.29 | -29.8% | +42.5% |
| marloes_ev_on_solar | 3000 | 2700.0 | 5700.0 | 103.12 | 252.90 | 252.90 | -149.78 | -59.2% | +145.2% |
| sander_heat_pump | 4200 | 2601.5 | 6801.5 | 498.96 | 678.87 | 678.87 | -179.91 | -26.5% | +36.1% |
| reference, car at night | 3500 | 2160.0 | 5660.0 | 447.11 | 623.50 | 623.50 | -176.39 | -28.3% | +39.5% |
| reference, car on surplus | 3500 | 2160.0 | 5660.0 | 88.93 | 202.03 | 202.03 | -113.10 | -56.0% | +127.2% |
| reference, heat pump 12000 | 3500 | 3468.7 | 6968.7 | 284.82 | 470.46 | 470.46 | -185.64 | -39.5% | +65.2% |

The understatement runs from 26.5 to 59.2 percent of the correct answer, always
downward. `docs/decisions.md` records 28 to 54 percent from the three reference
shapes alone; the six asset-bearing households here widen that at both ends.

Two checks that the harness measures the right thing. The three households with
no asset move by exactly zero under both repairs, so this is asset-gated and not
a general shift. And `rob_fixed_contract` at 623.50 and the reference household
with a night-charging car at 623.50 agree to the cent, which is chapter 17's
claim that a car charging at night moves the figure by nothing, arrived at from
a different direction. Both of those held in all three passes, at three
different absolute values.

Two things the table settles.

**Repair 1 and repair 2 produce the same number. Every time, to the cent.** The
gap column for repair 2 is 0.00 on all nine rows, and the base the carve-out
recovers is the base the golden file states, to six decimals. This is not a
coincidence of these households. A is independent of the base in every asset the
model has: a night or arrival car draws `annual_km / 100 * kwh_per_100km`
whatever else the house does, a solar car's grid top-up is defined as the
shortfall against that same figure so the two sum to it exactly, and the heat
pump's consumption is a function of the temperature series and the COP curve
alone.

So the two repairs are the same arithmetic reached from two directions. Choosing
between them is not a choice about accuracy. It is a choice about who does the
subtraction and whether it is visible.

**The error is larger than the uncertainty the product admits to.** The headline
is shown as a band, so the honest question is whether the two bands overlap.
Percentiles from the 243-cell sensitivity grid, p10 / p50 / p90:

| household | today | repair 1 and 2 | bands overlap |
|---|---|---|---|
| marloes_ev_at_night | 457.11 / 573.17 / 715.46 | 658.00 / 795.03 / 944.64 | yes |
| marloes_ev_on_solar | 66.80 / 109.31 / 167.75 | 203.02 / 252.95 / 311.87 | no |
| sander_heat_pump | 399.28 / 498.88 / 608.31 | 555.82 / 679.86 / 806.91 | yes |
| reference, car at night | 358.23 / 463.91 / 587.34 | 517.26 / 629.00 / 758.84 | yes |
| reference, car on surplus | 53.69 / 96.93 / 151.40 | 158.82 / 204.61 / 257.20 | no |
| reference, heat pump 12000 | 227.81 / 294.84 / 382.28 | 392.84 / 473.04 / 573.65 | no |

In three of the six there is no overlap at all. The correct answer sits outside
the whole range the product tells the visitor it might be in. The same three
were the non-overlapping three in all three passes.

## It is not only the euro figure. Advice disappears.

The double count raises modelled consumption, which raises the self-consumption
rate, which is the input two of the four live rules test. Rule ids fired by
`ampeer_advice.advise` for the same six households, at nine filled fields:

| household | self-consumption honest / today | fired honestly | fired today |
|---|---|---|---|
| marloes_ev_at_night | 0.2647 / 0.4842 | SHIFT_FLEXIBLE_LOAD, CHARGE_EV_ON_SURPLUS, CONSIDER_DYNAMIC_CONTRACT | CHARGE_EV_ON_SURPLUS, CONSIDER_DYNAMIC_CONTRACT |
| marloes_ev_on_solar | 0.7661 / 0.9046 | none | none |
| sander_heat_pump | 0.4977 / 0.6308 | CONSIDER_DYNAMIC_CONTRACT, BATTERY_DOES_NOT_PAY_BACK | BATTERY_DOES_NOT_PAY_BACK |
| reference, car at night | 0.3410 / 0.5274 | SHIFT_FLEXIBLE_LOAD, CHARGE_EV_ON_SURPLUS, CONSIDER_DYNAMIC_CONTRACT | CHARGE_EV_ON_SURPLUS, CONSIDER_DYNAMIC_CONTRACT |
| reference, car on surplus | 0.7864 / 0.9060 | none | none |
| reference, heat pump 12000 | 0.5027 / 0.6989 | CONSIDER_DYNAMIC_CONTRACT, BATTERY_DOES_NOT_PAY_BACK | none |

Four of the six lose advice, and five rules are lost across them:
`SHIFT_FLEXIBLE_LOAD` twice, `CONSIDER_DYNAMIC_CONTRACT` twice, and
`BATTERY_DOES_NOT_PAY_BACK` once.

Four of those five are free routes, which `CLAUDE.md` says are always shown
first, also when they earn Ampeer nothing. The fifth is the one CLAUDE.md calls
a valid and required outcome: the reference household with a heat pump is told,
honestly, that a battery does not pay back, and after the double count it is
told nothing at all. Both of the sentences it loses are the ones that sell
nothing.

The reference household with a car at night is the row to watch across the three
passes, and it is the reason this count is quoted as a count rather than as a
constant. Its honest self-consumption sits on the 0.35 threshold that
`SHIFT_FLEXIBLE_LOAD` tests: 0.3320 in the first pass, just under, so the rule
was lost; 0.3809 in the withdrawn second, just over, so it was not; 0.3410 in
the model that ships, just under again. Which side of that line it falls on is a
property of the production model and not of the double count. What does not move
is that every rule lost anywhere in this table is one that sells nothing.

## The question repair 2 actually turns on

Repair 2 subtracts, and the subtraction can leave too little. There are two
boundaries, and only one of them is obvious.

**The hard boundary.** `Household.__post_init__` refuses a non-positive annual
consumption, verified directly: 0.0 and -660.0 both raise
`annual_consumption_kwh must be positive`, 1.0 is accepted. Nothing in
`backend/advice/views.py` catches `ValueError`. So today a carve-out that goes
negative would surface as a 500 rather than as a sentence. That is what "needs a
rule for what happens when the carve-out leaves too little" means concretely:
the rule does not exist, and its absence is not currently a message.

**The boundary that bites first, and it is derivable rather than invented.** The
model does not simply scale a profile. `apply_presence` moves a shiftable block
of 1 kWh a day out of the 11:00 to 15:00 window, and it clamps: it moves
`min(block_kwh, available)`, where available is what that day's window actually
holds. Once the base is small enough that the window holds less than the block,
the presence lever stops working, silently and with no error. Chapter 3 of
`docs/methodologie.md` calls that lever the largest single factor in
self-consumption.

Smallest annual base at which the whole block still moves, found by bisection on
the real profile and on the flat one:

| profile | block 0.5 kWh | block 1.0 kWh | block 2.0 kWh |
|---|---|---|---|
| flat | 1095.0 | 2190.0 | 4380.0 |
| NEDU E1A, every day of the year | 1275.2 | 2550.3 | 5100.6 |
| NEDU E1A, half the days | 1026.3 | 2052.6 | 4105.2 |

The flat row is exactly `block x 365 x 6`, which is what a flat profile must
give and is the arithmetic check on the bisection. 1.0 kWh is the model's own
calibrated block; 0.5 and 2.0 are the ends of the range the sensitivity grid
already varies it over, so the band around 2550 runs 1275 to 5101 and comes from
the model rather than from taste. None of these figures moved when the
production fallback changed, because they are a property of the consumption
profile alone.

How hard it bites below that, on the real profile at the calibrated 1 kWh:

| residual base kWh | days the block does not fully move | worst day's midday window |
|---|---|---|
| 2550 | 1 | 1.000 kWh |
| 2200 | 134 | 0.863 kWh |
| 2000 | 211 | 0.784 kWh |
| 1500 | 350 | 0.588 kWh |
| 1000 | 365 | 0.392 kWh |

**So the boundary is 2550 kWh of residual base, with the model's own band on it
running from 1275 to 5101.** As a condition on the visitor's input: the bill
total must be at least the modelled asset plus 2550.

Worth saying plainly, because it stops this reading as a new problem: the golden
household `large_array_small_use` runs at 2200 kWh today with no asset at all,
so it already sits 134 days a year below this floor. The floor is not created by
repair 2. Repair 2 makes it reachable by households that are nowhere near it on
their own.

### How often the carve-out leaves too little

Swept over a grid: bill totals 1500 to 12000 kWh in steps of 100, heat demands
4000 to 20000 kWh in steps of 500 turned into electricity by the model's own COP
curve, and the car at the 2160 kWh the model always assumes because it never
asks. Share of grid cells whose residual falls below the floor:

| asset | modelled asset kWh | needs a bill total of | below 2550 | below 5101 | below 1, impossible |
|---|---|---|---|---|---|
| car only | 2160 | 4710 | 31.1% | 54.7% | 6.6% |
| heat pump only | 1156 to 5781 | 3707 to 8332 | 43.1% | 67.2% | 19.2% |
| car and heat pump | 3316 to 7941 | 5867 to 10492 | 63.5% | 86.4% | 39.4% |
| all three combined | | | 53.0% | 76.5% | 29.0% |

The honest caveat on that 53 percent: the grid is uniform and Dutch households
are not. A household that owns a car and a heat pump does not have a 1500 kWh
bill, so the low corner is heavily over-represented and the true share is lower,
probably much lower. The figure that does not depend on a distribution is the
third column. A car alone needs a bill of 4710 kWh before the carve-out is safe.
A car and a 12000 kWh heat pump need 8000. Those are the numbers to hold against
your own sense of who fills this form in.

None of the nine households in the first table hits the floor. The smallest
residual after carving is 3000 kWh.

### Where repair 2 stops being better than doing nothing

This is the finding that changes the shape of the decision.

Today's reading enters a base too high by the real asset, `A_real`. Repair 2
enters a base off by `A_real - A_model`. So repair 2 is the better of the two
only when `A_real > A_model / 2`, and below that it is worse than leaving the
bug alone. For the car, `A_model` is fixed at 2160 kWh because the kilometres are
never asked, so the crossing point is a real number about real drivers.

Reference household, night charging, against the 623.50 the model gives when the
base is entered correctly:

| real car, km a year | real car kWh | today | repair 2 | error today | error repair 2 |
|---|---|---|---|---|---|
| 3000 | 540 | 576.40 | 770.85 | -47.10 | +147.36 |
| 6000 | 1080 | 531.27 | 725.44 | -92.23 | +101.94 |
| 6200 | 1116 | 528.33 | 721.85 | -95.17 | +98.35 |
| 6400 | 1152 | 525.41 | 718.27 | -98.08 | +94.77 |
| 9000 | 1620 | 487.97 | 672.99 | -135.52 | +49.50 |
| 12000 | 2160 | 447.11 | 623.50 | -176.39 | 0.00 |
| 15000 | 2700 | 409.52 | 576.40 | -213.98 | -47.10 |
| 20000 | 3600 | 353.02 | 502.23 | -270.47 | -121.26 |
| 25000 | 4500 | 301.95 | 434.28 | -321.55 | -189.22 |

**The crossing is between 6200 and 6400 kilometres a year**, in all three
passes, on three different production models. Below it repair 2 is measurably worse than
today. Above it, better, and by 20000 km it has more than halved the error. It
also changes the error's sign: today always understates, repair 2 overstates
below 12000 km and understates above it.

The heat pump does not have this problem, and the reason is worth naming. Heat
demand *is* asked in round two, so the carve-out figure is derived from the
visitor's own answer through the COP curve, and the only error left is the COP
model. The car is not asked. That single difference is what makes repair 2 well
founded for one asset and a guess for the other.

### What repair 1 costs when the visitor subtracts badly

Fair is fair: repair 1's error is however far the visitor's own subtraction is
off. Reference household, moving the entered base:

| base error | with a heat pump | with a car at night |
|---|---|---|
| -1000 kWh | 533.30 | 717.48 |
| -500 kWh | 501.30 | 669.22 |
| correct, 3500 | 470.46 | 623.50 |
| +500 kWh | 440.74 | 579.83 |
| +1000 kWh | 412.14 | 537.81 |

Roughly 6.1 euro per 100 kWh of mis-subtraction with a heat pump and 9.0 with a
car. A visitor who guesses their heat pump at 3000 kWh where the model would say
3469 lands within 30 euro of right; today's reading is 186 euro off. Repair 1
survives a sloppy subtraction comfortably. What it does not survive is a visitor
who cannot subtract at all and types the total anyway, which puts them silently
back on the "today" row.

## Recommendation

**Repair 2, with the floor written down, and with the car's annual kilometres
asked.**

The reasoning in the order the numbers support it.

Repair 1 and repair 2 give identical answers, so this is not an accuracy
argument. It is an argument about failure modes. Repair 1's failure mode is a
visitor who types the total anyway, and that visitor is indistinguishable from a
correct one: they land on the "today" row, lose between 26.5 and 59.2 percent of
their answer, and lose their free-route advice, with nothing anywhere reporting
a problem. That is the class of failure this repository keeps replacing with a
derived check: a wrong answer that produces no error. Repair 2's failure mode is
bounded, one-dimensional and inspectable: the residual error is exactly
`A_real - A_model`, and the boundary where it becomes unusable is 2550 kWh of
residual, derived above rather than chosen.

Asking the kilometres is not an extra, it is what makes repair 2 defensible. The
carve-out makes the 12000 km assumption load-bearing twice, once in what is
subtracted and once in what is added, and the crossing at 6300 km is entirely a
consequence of not asking. One integer field removes it. It also removes a
sentence chapter 4 currently has to carry, that a car nobody described is 2160
kWh against a household of 3500.

The floor needs a decision and not only a number. My suggestion, and it is only
that: below 2550 kWh of residual, do not refuse and do not carve. Fall back to
reading the answer as the base, and say so on the confidence line that is
already on the screen. A refusal at that point tells a real household that its
real bill is wrong.

## The strongest argument against my own recommendation

Repair 2 raises what every asset-owning household is told by 36 to 145 percent
of today's figure, and it does so entirely inside the model, where the visitor
cannot see it. That is the direction that makes Ampeer's own case stronger, and
chapter 17 already has the sentence for exactly this situation: being careful in
the direction that suits us is not careful, it is convenient. Under repair 1 the
visitor owns the subtraction and can check it. Under repair 2 the largest single
correction in the product becomes another undisclosed assumption, resting on an
asset size the model guesses, and the household has no way to tell whether the
number went up because the model got more honest or because it got more
confident.

Three specific things make that argument harder to dismiss than it sounds.

Below 6300 kilometres a year repair 2 is measurably worse than shipping the bug,
by up to 147 euro in the wrong direction on the reference household. It is the
only one of the three readings that can overstate the shock, and overstating is
the failure this product can least afford.

Repair 2 needs a fallback rule that repair 1 does not need at all, and on the
uniform grid that rule fires on 53 percent of cells and 63.5 percent for a
household with both assets. Even granting that the real distribution is far
kinder, that is a new, frequently taken, undesigned path in the part of the
system where a mistake produces a plausible number rather than an error.

And repair 1's supposed weakness, that somebody with one meter and one total
cannot produce the figure, is asserted rather than measured, in
`docs/decisions.md` and here alike. The sensitivity table above says a 500 kWh
mis-subtraction costs 30 euro, so an approximate answer is worth far more than
the argument assumes. Nobody has put a form in front of anybody that says "uw
jaarverbruik, zonder de warmtepomp, een schatting is genoeg".

That last one is testable and neither of us has tested it. If both wordings can
be put in front of twenty people before this is settled, that measurement is
worth more than everything above it.

## Method, and how it was verified

Every figure was produced by driving the real engine. The harness is
`tests/test_methodology.py::_reference_shock` extended to the golden set:
`FallbackProvider(2025).hourly_series`, then `production_series`, then
`compose_consumption` on a flat fractions array, then `simulate`, then
`annual_cost(flows, scenario_2027_tariffs(dynamic=False)) - annual_cost(flows,
baseline_tariffs())`. Bands come from `ampeer_sim.simulate.run_advice` and fired
rules from `ampeer_advice.advise.advise` at nine filled fields. The floors come
from `scale_to_annual` plus the same `MIDDAY_WINDOW` and `window_mask` that
`apply_presence` uses, bisected to sixty iterations. Asset sizes were measured
two independent ways that agree to three decimals: by composing with and without
the asset, and by calling the asset models directly the way a carve-out must.

The script lived in a scratch directory rather than in the repository, because
this lane owned only this file. Two notes for anyone redoing it. The golden EV
households drive 15000 km a year, a field in `households.json` that the API
never asks for and never sets, so their 2700 kWh car is larger than the 2160 kWh
car every real visitor gets. And the flat profile is used for the euro tables so
the figures line up with the ones recorded in `docs/decisions.md`, while the
floors are computed on the real NEDU E1A profile from
`data/nedu-profiles-2025.csv`, which is gitignored and only present on a machine
that has run `tools/ingest_profiles.py`. A floor derived from a flat day would
be a floor about a household that does not exist.

Verification, in full.

- The euro table and the fired-rules table were each computed twice in separate
  processes on the current tree and diffed: identical. The floors table likewise.
- The flat row of the floors table matches its closed form `block x 365 x 6`
  exactly, which is the arithmetic check on the bisection.
- The whole analysis was run three times against three materially different
  production models, as described at the top. Every structural conclusion held
  and every euro figure moved each time, which is the honest summary of how much
  weight the euro columns will bear. The euro tables here are the third pass,
  against the code that ships; the second pass measured a window that was
  withdrawn before it landed and its figures are not in this document.
- Against the first production model the three reference figures reproduced
  `docs/decisions.md` exactly: 456 / 634, 291 / 479, 97 / 212. That is the
  evidence that this harness is the same calculation the decision was recorded
  from.
- The `ValueError` boundary was confirmed by calling `Household` directly rather
  than reasoned about.
- `tests/test_portability.py`, `tests/test_decisions.py` and `tests/test_plans.py`
  were run after this file was written and pass. While the second pass was being
  written,
  `tests/test_methodology.py::test_the_document_says_the_car_is_added_to_the_figure_you_type`
  was red on account of the production-model change described at the top, which
  was another lane's work and not caused by anything here. It is green again:
  chapter 4 now quotes 447 against 623, the figures the shipping model produces
  and the ones in the first table above.
