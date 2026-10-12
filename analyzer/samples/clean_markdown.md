# Lightweight Fault Detection for Small Wind Turbines Using Vibration Spectra

## Abstract

Small wind turbines are often installed far from maintenance teams, so faults in the gearbox or bearings may go unnoticed until the turbine stops. We study whether a lightweight detector running on a low-cost microcontroller can flag developing faults early enough to plan a visit. We collected vibration data from twelve turbines over fourteen months and labelled each week as healthy or faulty using maintenance records. Our detector computes a small set of spectral features and compares them with a per-turbine baseline learned during the first month of operation. On held-out turbines it detected nine of eleven recorded faults with a median warning time of nineteen days, while raising one false alarm per turbine per year. The detector needs less than forty kilobytes of memory and runs within the power budget of the existing data logger. These results suggest that simple, per-turbine baselines are a practical first step before more complex models are deployed in the field.

## Introduction

Distributed wind generation has grown steadily, and many small turbines are now operated by farms, schools and cooperatives rather than utilities [1]. Unlike large turbines, they rarely have a condition monitoring system (CMS), because commercial systems cost more than the turbine itself [2]. Faults that develop slowly, such as bearing wear or gear tooth damage, therefore tend to be found only after a failure.

Vibration analysis is the most widely used technique for detecting such faults in rotating machinery [3]. Spectral features around the gear mesh frequency and the bearing defect frequencies change well before a failure becomes audible [4]. However, most published detectors are trained on laboratory test rigs and assume a powerful computer next to the machine [5].

This paper makes two contributions. First, we describe a detector small enough to run on the microcontroller that already logs power output. Second, we evaluate it on field data from turbines that were not used to design it, and we report both missed faults and false alarms.

## Methods

We installed a single-axis accelerometer on the main bearing housing of twelve turbines rated between 3 and 10 kW. The data logger records one second of vibration at 4 kHz every ten minutes. Maintenance records were used to mark the week of each confirmed fault; the four weeks before a fault were labelled as faulty and all other weeks as healthy.

For each recording we compute the energy in five frequency bands centred on the shaft frequency, its first two harmonics and the two bearing defect frequencies given by the manufacturer. During the first month a turbine operates, the detector stores the mean and standard deviation of each band. Afterwards it raises an alarm when the weekly median of any band exceeds the baseline by more than four standard deviations for two consecutive weeks. The design follows the per-machine baseline approach of earlier work [4], simplified to fit a fixed memory budget.

We split the turbines by site: seven turbines from two sites were used to choose the band widths and the threshold, and five turbines from a third site were held out for the final evaluation, as summarised in Table 1.

Table 1: Turbines used for design and held-out evaluation.

## Results

On the five held-out turbines the detector found nine of the eleven faults recorded in the maintenance log. The median warning time was nineteen days before the recorded fault, with a range from four to forty-one days. Figure 1 shows the band energy of one turbine in the months before a bearing replacement.

Figure 1: Band energy around the outer-race defect frequency before a bearing replacement.

The two missed faults were a blade crack and a yaw motor failure, neither of which produces a clear signature at the bearing housing. Over the held-out period the detector raised six false alarms, about one per turbine per year. Most of them occurred during storms with sustained high wind, when the shaft speed stayed above the range seen during the baseline month.

## Discussion

The results show that a per-turbine baseline with a fixed threshold is enough to detect most drivetrain faults on small turbines, at a false alarm rate that a maintenance team can accept. The main limitation is that faults outside the drivetrain are not visible to a single accelerometer on the bearing housing. A second limitation is that the baseline month must not contain a developing fault; on older turbines this cannot be guaranteed.

Future work will normalise band energy by shaft speed to reduce false alarms during storms, and will compare the detector with a small learned model under the same memory budget.

## References

[1] A. Rivera and M. Holt, "Small wind turbines in community energy projects," Renewable Energy Review, vol. 12, pp. 44-58, 2021.
[2] K. Osei, "The cost of condition monitoring for distributed generation," Energy Systems, vol. 9, no. 3, pp. 210-222, 2020.
[3] P. Lindqvist, Vibration Analysis of Rotating Machinery, 2nd ed. Oslo: Nordic Technical Press, 2018.
[4] S. Haddad and R. Mendes, "Per-machine baselines for early gearbox fault detection," Mechanical Systems Letters, vol. 7, pp. 1-9, 2022.
[5] J. Park, L. Chen and D. Novak, "A survey of data-driven fault detection for wind turbines," Journal of Wind Engineering, vol. 30, pp. 300-327, 2019.
