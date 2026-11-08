# Chapter 8 responses — chapter-end integration completed

Author's workflow: save each response verbatim with brief initial notes, then immediately present the next section. Defer source checks, rewriting, TeX integration and full review until the end of the chapter. Reinforced by the author after section 8.1 because per-section processing was taking too long.

## 8.1 Aims — author's response

> To train a classifier, data needs to be sorted into labelled groups. This thesis examines classifiers trained on three main methodologies of sorting: manual labelling - a human reviewer decides which windows belongs in which of a pre-determined categorisation, cluster-derived labels - windows are grouped automatically and clusters are developed as groups where members are more similar to each other than they are to members outside, and reviewed candidates - where human-chosen exemplars define the initial categories and the remaining data is grouped according to its similarity to the predefined exemplars. The main aim of training a classifier is to examine its potential to identify events that pass human review, beyond the data used for initial training. Training data needs to encompass all possible cases and variations of the data, accepted data is insufficient, rejected data must also comprise a stake of the training set. Three main approaches are used to build a classifier model. The first is the Random Forest methodology. Each window is statistically evaluated and represented by a collection of its results. A tree is a random pathway that computes a verdict based on thresholds all of the statistical measures pass or fail. A window is then classed based on the majority vote of the classifications of a group of trees, or a forest. This classifier is the easiest to train. The next classifier is a Convolution Neural Network, which takes each window, transformed into 2D matrix of values (in this thesis using Gramian Angular Field Imaging), which is then decomposed, and filtered through many processes to identify edges, values and recurring themes in the images to pattern-match them to their respective categories. The third and final technique used is a relatively new classification method (reference) called MiniRocket. This methodology takes a family of kernels, maps the similarity of each window of data to the kernels, and classifies it according to how it scores. [this is maybe too much information since they are explained earlier in the thesis, check and make sure it is accurate, make more brief if need be]. The models, once trained, are evaluated on their performance on unseen datasets. The ultimate evaluation of the validity of their results is based on human review [is this true? how do we evaluate them? pre-categorised training data set aside? fix please, also include what purple notes suggest].

### Initial notes for chapter-end review

- Clarify reviewed candidates: detector/seed proposals labelled by the researcher, rather than automatic assignment to exemplar-defined categories. R4 predicts interesting/not, not named waveform classes.
- Shorten model theory in Aims; refine tree learning, CNN encodings, and MiniRocket filter-response features plus ridge classifier. Use the existing Dempster et al. (2021) citation. Earlier MiniRocket theory is still a purple block, so do not assume it is already finished.
- Explain evaluation against labels excluded from training, including independent blind labels and the original frozen M4 exam. Not every prediction receives a fresh human review. Replace “all possible cases” with representative variation.
- At integration check actual saved forest settings (the purple note says 100 trees, while the current factory defaults to 300), protocol-specific shuffle counts, and the historical MJu26a excerpt/fold dependence. MiniRocket's saved manifest records about 5,000 features and a 512-point input; do not confuse input points with physical seconds.

## 8.2 Methods — author's response

> Training Labels. Training data came from three main sources: [list as you have it]. All datasets excluded windows marked as artefacts, duplicates were also excluded. Model inputs. [as you have it with more detail, include image/s, particularly to show gaf imagery, image of models as a diagram underneath the sharkfin waveform is good]. Evaluation. The models were evaluated and screened through a set of progressively stronger tests. [not sure what the tests were, can you finish this section and 'controls and scoring' in my prose].

### Initial notes for chapter-end review

- Insert the supplied three-source label list. Check exclusions by experiment rather than assuming every model used identical artefact/duplicate handling.
- Expand model inputs briefly; include GAF imagery and retain/improve the requested waveform-to-model diagram. Inspect existing figures at chapter end.
- Complete evaluation in the author's cadence: later time blocks, unseen channels, blind human-labelled windows, leave-one-recording-out events and the original frozen M4 exam. Explain training/test separation and distinguish the different experimental populations.
- Complete controls and scoring: protocol-specific shuffle counts, majority class, detector agreement and size/noise baselines; explain balanced accuracy, AUC, precision, recall and macro F1 as needed. Do not turn the classifier's agreement with subjective labels into a biological validation claim.

## 8.3.1 Cluster labels against manual labels — author's response

> Two random forest models were trained on the same signal features. The difference was with how the datasets were labelled. The first classifier was trained on data manually labelled 'interesting' or 'not interesting'. This model scored an unseen-channel macro F1 of 0.793. The second model was trained on categories formed by a clustering, with a human adjudicated cutline. The resulting F1 score was 0.635. The cluster categories, for comparison, were ultimately deemed either 'interesting' or 'not interesting'. 979 of the 1271 interesting training windows, 77%, were categorised into clusters deemed 'not interesting', implying that the cluster model had labels that significantly disagreed with the human reference. [can you emphasise here]. A later version of the model used seven waveform-shape clusters mapped to interesting and not interesting. The comparison can be seen in Table __. The manual model was found to be selective, positive predictions were accepted but many interesting windows were missed. The cluster model was better at identifying interesting windows, but also flagged many rejected ones. [elaborate more here]. [section 3 reword what you have in my prose, add more detail to the entire 8.3.1 as ive missed]\

### Initial notes for chapter-end review

- Emphasise that the first comparison tests the clustering/label translation as well as the classifier: the 77% disagreement was already present in its training targets. Avoid a general claim that clustering itself fails.
- Clarify the distinction between choosing a clustering cut and mapping clusters to human interesting/not labels.
- Insert the like-for-like blind comparison table with its population, and explain selective/manual versus permissive/cluster predictions using precision and recall.
- Complete the conclusion in the author's cadence: above-shuffle performance, practical review-queue trade-offs, incomplete replacement of human labels, weaker M2_concat generalisation, and the limits of partly overlapping earlier training/evaluation data.

## 8.3.2 The CNNs — author's response

> The convolutional neural networks were trained on time series data transformed under Gramian angular field imaging (see Chapter 3). Four distinct types of image encodings were generated for each window: a gramian angular summation field (GASF), a gramian angular difference field (GADF), a recurrence plot, and a fusion plot which combined each of the three prior images as individual red green and blue channels. On a set of data, split 80:20 for training and testing, the models scored with an accuracy of 91-92% on the test data. However, since the test windows were drawn from within and around the training data, signal content could be shared. Later tests on unseen data report more conservative estimates of models selective capabilites.

## Author's instruction to complete the chapter

> [fill the rest of the chapter as you described, in more detail, in my prose]

The author then requested the Chapter 8 discussion/conclusion before integration. The proposed seven-paragraph discussion was shown in full and approved with:

> sure that sounds good. continue

The approved discussion is retained in section 8.4 of chapters/08_rq3_classifiers.tex, with only TeX formatting changes. It covers learned labels across recordings, cluster mapping disagreement, the matched-data CNN comparison, weighted M4 results, single-reviewer uncertainty, the candidate-only evaluation scope and future named classes.

## Chapter-end integration — 7 November 2026

- Integrated responses 8.1–8.3.2 and completed the remaining results, methods and approved discussion in the author's cadence. All Chapter 8 purple recommendations were reviewed against the primary records, rather than copied literally.
- Shortened the model explanations in Aims, clarified that reviewed candidates receive human binary labels, and explained the held-out-label evaluation sequence.
- Added the paired forest blind-window table, with precision and recall to explain selective manual predictions versus permissive cluster predictions.
- Verified saved configurations: the original paired forests used 100 trees and 24 retained features; the revised shape forest used 300 trees and 26 features.
- Corrected the CNN table: the 0.78–0.83 balanced accuracies describe 429 pooled blind windows, not M2_aug alone. Added recurrence values on M2_concat and explained duration, threshold and training-overlap limits.
- Completed MiniRocket controls and baselines, distinguishing the 200-refit unweighted ridge null from the principal class-balanced model, the 1,689-candidate scalar baseline from a different event-only analysis, and the 12-event overlapping MJu26a excerpt.
- Included the matched-data CNN results and their uncertainty. They show no clear performance gap from R4 on shared folds; they were not added retrospectively to the original M4 examination.
- Preserved the frozen M4 scoring population: 290 reviewed → 276 answered → 269 mapped binary labels → 257 readable scored cases. The seven seed verdicts were omitted by the frozen classifier mapping; the five artefacts were negative. Candidate-acceptance estimates used 276 answered verdicts, counting seed as accepted. No model, threshold, label map or historical score was changed.
- Corrected the R4 example figure and caption to 52 hits, six false alarms, seven misses and 192 correct rejections, matching the 257-case classifier result.
- Added a vector waveform-to-model diagram with actual GASF/GADF/recurrence/fusion encodings of an explicitly schematic waveform. The feature bars and filter example are illustrative. Both updated figure previews were inspected.
- Replaced the outdated claim that 94% self-agreement is a numerical ceiling for balanced accuracy with the approved distinction between these measures. Avoided claiming a biological event/noise boundary or continuous-scan recall.
- Updated the exam appendix and its methodology exposure date, numerical ledger and context audit. Verified TeX structure, references, image paths and key numeric claims statically; the full thesis PDF was not rebuilt.

## Next response

Chapter 9, section 9.1 Aims. Resume the rapid collection workflow: present context, save the author's response with brief notes, then present the next section. Defer Chapter 9 integration until its end unless the author requests otherwise.

## 8 November — author's replacement discussion

The author supplied a revised 8.4 and requested that the rest of the earlier second paragraph and limitations remain. Integrated the replacement introduction, label-source comparison, matched-data CNN interpretation and future-family paragraph, preserving the author's cadence. Clarified the initial four cluster categories and revised seven categories, each translated to binary labels.

The author specifically asked whether the models scored the M4 queue before or after human judging, and what 0.93, 0.77 and 0.96 meant. The revised discussion now states the frozen-model → blind human review → model scoring chronology. Balanced accuracy 0.93 is the mean of the two class recalls; it is not ordinary accuracy. The weighted 0.77 uses the same scored cases and predictions with population weights. AUC 0.96 describes ranking under those weights.

For the requested family-size example, the named g-11 snapshot supplies 42 families / 817 assigned de-duplicated Library events, mean 19.5. Its human-accepted subset supplies 41 families / 519 assigned accepted events, mean 12.7. The old manually labelled fixed windows are a separate training source, not additional members of this grouping. A collection target of hundreds per family can be proposed, but there is no verified universal 500-per-family requirement; held-out learning curves should establish adequacy.

The author's 9.1 draft is saved in CHAPTER_09_RESPONSES.md. The author explicitly postponed 9.2 while the new HPC returns were audited, analysed and packaged for recovery.

Drop-transfer results belong in Chapter 7's seed-search results, separate from the frozen Chapter 8 classifier exam. New 2 Hz detector returns are reported in Chapter 10, with incomplete settings excluded from complete-coverage comparisons. Neither is used to rewrite the historical M4 classifier scores.
