# project-mode run 2026-09-21

backup verified: C:\Users\mmebr\Documents\CNN\DATA\db\backups\20260921-171549.sqlite (4,349,952 bytes)

L_LM checks:
exists · DATA/derived/channels/L_LM_Jul_26_J_raw_fs10
readable · 5 channel files load (1-D, mmap)
shape · 5 channels × 22,892,769 samples
fs · fs 10.0 Hz (from manifest)
held_out · not the held-out recording
excerpt · not an excerpt of any registered recording (r > 0.99 with a one-sample peak against every comparable channel)
not_registered · not registered yet
hash · 4e6d25d1a9ffef187e5c8a1fb033c3315b650253
fs is inferred: 10.0 Hz is inferred, not read from the file: the .mat carries a scalar MATLAB duration, not a timestamp vector; verified against catalogue id 385 (Mushroom_260720, a 10:1 decimated four-hour excerpt of CH2 at sample 15,777,590, r = 0.9995) - see lionsmane12.py
registered Mushroom_260720_0509_4hrs_CH14_fs1.mat CH0 (id 385) is a 10:1 excerpt of this recording's CH2 at sample 15,777,590 (r = 0.9995); it will be linked, its id kept

M1: HTTP 200 in 31s -> {"id": 545, "ids": [545, 546, 547, 548, 549, 550, 551, 552, 553, 554, 555, 556, 557], "warnings": ["fs unknown: no manifest.json carries it \u2014 supply the sampling rate at registration (it is recorded as inferred)", "no manifest.json: the recording is labelled 'M1.mat' after its directory; pass source_file to override"], "excerpts": [], "excerpt_of": null, "note": "written to the project database"}

M100: HTTP 200 in 24s -> {"id": 558, "ids": [558, 559, 560, 561, 562, 563, 564, 565, 566, 567, 568, 569, 570], "warnings": ["fs unknown: no manifest.json carries it \u2014 supply the sampling rate at registration (it is recorded as inferred)", "no manifest.json: the recording is labelled 'M100.mat' after its directory; pass source_file to override"], "excerpts": [], "excerpt_of": null, "note": "written to the project database"}

M101_t: HTTP 200 in 17s -> {"id": 571, "ids": [571, 572, 573, 574, 575, 576, 577, 578, 579, 580, 581, 582, 583], "warnings": ["fs unknown: no manifest.json carries it \u2014 supply the sampling rate at registration (it is recorded as inferred)", "no manifest.json: the recording is labelled 'M101_t.mat' after its directory; pass source_file to override"], "excerpts": [], "excerpt_of": null, "note": "written to the project database"}

MJu26a: HTTP 200 in 0s -> {"id": 584, "ids": [584, 585, 586, 587, 588, 589, 590, 591, 592, 593, 594, 595, 596, 597, 598, 599], "warnings": ["sampling is not uniform: t is not uniform: dt min 0.124, median 0.138, max 2.83 (units as stored in the .mat); fs below is 1/median(dt)"], "excerpts": [], "excerpt_of": null, "note": "written to the project database"}

matrix_profile mp_v2_M2_aug_concat_fs1_CH0_WIN10min.npz: HTTP 422 {"detail": "{'message': \"matrix_profile 'mp_v2_M2_aug_concat_fs1_CH0_WIN10min.npz' fails 1 check(s)\", 'candidate': {'kind': 'matrix_profile', 'path': 'Results/Detection/matrix_profile/mp_v2_M2_aug_concat_fs1_CH0_WIN10min.npz', 'name': 'mp_v2_M2_aug_concat_fs1_CH0_WIN10min.npz', 'facts': {'bytes': 4097, 'legacy_"}

matrix_profile mp_v2_M2_aug_concat_fs1_CH0_WIN1min.npz: HTTP 422 {"detail": "{'message': \"matrix_profile 'mp_v2_M2_aug_concat_fs1_CH0_WIN1min.npz' fails 1 check(s)\", 'candidate': {'kind': 'matrix_profile', 'path': 'Results/Detection/matrix_profile/mp_v2_M2_aug_concat_fs1_CH0_WIN1min.npz', 'name': 'mp_v2_M2_aug_concat_fs1_CH0_WIN1min.npz', 'facts': {'bytes': 56616, 'legacy_si"}

matrix_profile mp_v2_M2_concat_fs1_CH0_WIN10min.npz: HTTP 200 {"id": 1, "recording_id": 33, "warnings": []}

matrix_profile mp_v2_M2_concat_fs1_CH0_WIN1min.npz: HTTP 200 {"id": 2, "recording_id": 33, "warnings": []}

matrix_profile mp_v2_M2_concat_fs1_CH0_WIN5min.npz: HTTP 200 {"id": 3, "recording_id": 33, "warnings": []}

matrix_profile mp_v2_M2_concat_fs1_CH0_WIN5min_span0-10000.npz: HTTP 200 {"id": 4, "recording_id": 33, "warnings": []}

matrix_profile mp_v2_M2_concat_fs1_CH0_WIN60min.npz: HTTP 200 {"id": 5, "recording_id": 33, "warnings": []}

matrix_profile mp_v2_M2_concat_fs1_CH13_WIN34min.npz: HTTP 200 {"id": 6, "recording_id": 46, "warnings": []}

matrix_profile mp_v2_M2_concat_fs1_CH2_WIN4.704min.npz: HTTP 200 {"id": 7, "recording_id": 35, "warnings": []}

matrix_profile mp_v2_M2_concat_fs1_CH2_WIN50min.npz: HTTP 200 {"id": 8, "recording_id": 35, "warnings": []}

matrix_profile mp_v2_Mushroom_260720_0509_4hrs_CH14_fs1_CH0_WIN10min.npz: HTTP 422 {"detail": "{'message': \"matrix_profile 'mp_v2_Mushroom_260720_0509_4hrs_CH14_fs1_CH0_WIN10min.npz' fails 1 check(s)\", 'candidate': {'kind': 'matrix_profile', 'path': 'Results/Detection/matrix_profile/mp_v2_Mushroom_260720_0509_4hrs_CH14_fs1_CH0_WIN10min.npz', 'name': 'mp_v2_Mushroom_260720_0509_4hrs_CH14_fs1_C"}

matrix_profile mp_v2_Mushroom_260720_0509_4hrs_CH14_fs1_CH0_WIN1min.npz: HTTP 200 {"id": 9, "recording_id": 385, "warnings": []}

matrix_profile mp_v2_Mushroom_260720_0509_4hrs_CH14_fs1_CH0_WIN3min.npz: HTTP 200 {"id": 10, "recording_id": 385, "warnings": []}

window_matrix wm_v1_M2_aug_concat_fs1_CH0_WIN5min_STEP100pct.npz: HTTP 200 {"id": 11, "recording_id": 1, "warnings": []}

window_matrix wm_v1_Mushroom_260720_0509_4hrs_CH14_fs1_CH0_WIN10min_STEP100pct.npz: HTTP 200 {"id": 12, "recording_id": 385, "warnings": []}

window_matrix 0.01_percent_M2_concat_fs1.mat_step0.5.csv: HTTP 200 {"id": 13, "recording_id": 33, "warnings": ["legacy CSV window matrix: no manifest fields; the recording is inferred from the file name and must be checked by eye"]}

window_matrix 0.01_percent_M2_concat_fs1_consecutive.csv: HTTP 200 {"id": 14, "recording_id": 33, "warnings": ["legacy CSV window matrix: no manifest fields; the recording is inferred from the file name and must be checked by eye"]}

window_matrix M2_concat_fs1_10min_27118wins_consecutive.csv: HTTP 200 {"id": 15, "recording_id": 33, "warnings": ["legacy CSV window matrix: no manifest fields; the recording is inferred from the file name and must be checked by eye"]}

window_matrix features - Copy.csv: HTTP 200 {"id": 16, "recording_id": null, "warnings": ["legacy CSV window matrix: no manifest fields; the recording is inferred from the file name and must be checked by eye", "no registered recording is named in the file name"]}

window_matrix features.csv: HTTP 200 {"id": 17, "recording_id": null, "warnings": ["legacy CSV window matrix: no manifest fields; the recording is inferred from the file name and must be checked by eye", "no registered recording is named in the file name"]}

window_matrix features_graph.csv: HTTP 200 {"id": 18, "recording_id": null, "warnings": ["legacy CSV window matrix: no manifest fields; the recording is inferred from the file name and must be checked by eye", "no registered recording is named in the file name"]}

model GADF_checkpoint.pth: HTTP 200 {"id": 19, "warnings": ["no provenance sidecar yet: training recipe, data and split are unknown until recorded here"]}

model GADF_cnn.pth: HTTP 200 {"id": 20, "warnings": ["no provenance sidecar yet: training recipe, data and split are unknown until recorded here"]}

model GASF_checkpoint.pth: HTTP 200 {"id": 21, "warnings": ["no provenance sidecar yet: training recipe, data and split are unknown until recorded here"]}

model GASF_cnn.pth: HTTP 200 {"id": 22, "warnings": ["no provenance sidecar yet: training recipe, data and split are unknown until recorded here"]}

model catch22_rf_prelabeled.joblib: HTTP 200 {"id": 23, "warnings": ["no provenance sidecar yet: training recipe, data and split are unknown until recorded here"]}

model fusion_cnn.pth: HTTP 200 {"id": 24, "warnings": ["no provenance sidecar yet: training recipe, data and split are unknown until recorded here"]}

model fusion_cnn_2.pth: HTTP 200 {"id": 25, "warnings": ["no provenance sidecar yet: training recipe, data and split are unknown until recorded here"]}

model fusion_cnn_3.pth: HTTP 200 {"id": 26, "warnings": ["no provenance sidecar yet: training recipe, data and split are unknown until recorded here"]}

model fusion_prediction_checkpoint.pth: HTTP 200 {"id": 27, "warnings": ["no provenance sidecar yet: training recipe, data and split are unknown until recorded here"]}

model fusion_prediction_cnn.pth: HTTP 200 {"id": 28, "warnings": ["no provenance sidecar yet: training recipe, data and split are unknown until recorded here"]}

model recurrence_checkpoint.pth: HTTP 200 {"id": 29, "warnings": ["no provenance sidecar yet: training recipe, data and split are unknown until recorded here"]}

model recurrence_cnn.pth: HTTP 200 {"id": 30, "warnings": ["no provenance sidecar yet: training recipe, data and split are unknown until recorded here"]}

model catalogue_classifier_16750c76ade64016.joblib: HTTP 200 {"id": 31, "warnings": ["no provenance sidecar yet: training recipe, data and split are unknown until recorded here"]}

model catalogue_classifier_31895944e26935a4.joblib: HTTP 200 {"id": 32, "warnings": ["no provenance sidecar yet: training recipe, data and split are unknown until recorded here"]}

model catalogue_classifier_3d7fd04e0904dcc5.joblib: HTTP 200 {"id": 33, "warnings": ["no provenance sidecar yet: training recipe, data and split are unknown until recorded here"]}

model catalogue_classifier_52520f7a898cb384.joblib: HTTP 200 {"id": 34, "warnings": ["no provenance sidecar yet: training recipe, data and split are unknown until recorded here"]}

model catalogue_classifier_ad10caaed29d1ad4.joblib: HTTP 200 {"id": 35, "warnings": ["no provenance sidecar yet: training recipe, data and split are unknown until recorded here"]}

model catalogue_classifier_f918586712c715e2.joblib: HTTP 200 {"id": 36, "warnings": ["no provenance sidecar yet: training recipe, data and split are unknown until recorded here"]}

drop_motif_store motifs: HTTP 422 {"detail": "{'message': \"drop_motif_store 'motifs' fails 1 check(s)\", 'candidate': {'kind': 'drop_motif_store', 'path': 'DATA/library_seed/drop_motifs5/motifs', 'name': 'motifs', 'facts': {'files': ['events.csv', 'manifest.json', 'snippets.npz'], 'detector': 'detect5', 'n_motifs': 410, 'manifest': {'kind': 'drop_motifs5', 'version': 1, 'n_motifs': 410, 'n_pure': 362, 'n_impure': 48, 'spans': [1, 3, 8, 10, 20,"}

catalogue_spreadsheet signal_catalog.xlsx: HTTP 200 {"id": 37, "warnings": []}

browser errors: []

Explore recordings now: M2_aug_concat_fs1.mat, M2_aug_concat_fs2.mat, M2_concat_fs1.mat, Fig2A_dt0p1.csv, L_LM_Jul_26_J_raw.mat, M1.mat, M100.mat, M101_t.mat, M4_aug_concat_fs1.mat, MJu26a.mat, Mushroom_260720_0509_4hrs_CH14_fs1.mat
