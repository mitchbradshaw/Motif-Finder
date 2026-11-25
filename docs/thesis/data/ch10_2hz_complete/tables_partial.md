| family | settings | MJu26a_fs2 real | MJu26a_fs2 sur. | SH_fs2 real | SH_fs2 sur. | SO_fs2 real | SO_fs2 sur. |
|---|---:|---:|---:|---:|---:|---:|---:|
| BEADs_invert_detect_v1 | 3 | 2,439 | 25,118 | 1,135 | 12,599 | 574 | 6,918 |
| OASIS_Deconvolution | 3 | 358,284 | 7,175 | 53,380 | 1,218 | 70,066 | 1,211 |
| Wavelet_detection_prototype | 3 | 167,199 | 214,236 | 27,632 | 38,601 | 23,185 | 37,972 |
| cnn_10min | 4 | 26,648 | 22,377 | 2,993 | 3,444 | 2,394 | 3,014 |
| cnn_1min | 4 | 226,525 | 467,918 | 17,618 | 99,610 | 10,446 | 81,817 |
| cnn_60min | 4 | 4,948 | 3,964 | 1,263 | 695 | 1,250 | 607 |
| deconvolved_troughs | 3 | 414,921 | 4,526 | 119,583 | 957 | 103,298 | 922 |
| drop_detection_v1 | 3 | 1,529 | 460 | 58 | 36 | 75 | 27 |
| drop_detection_v5 | 3 | 2,466 | 3,717 | 72 | 16 | 129 | 9 |
| matrix_profile | 1 | 62,527 | 7,248 | 22,148 | 6,015 | 80,053 | 10,042 |
| noise_threshold | 3 | 31,376 | 1,023 | 7,407 | 226 | 8,260 | 199 |
| signal_threshold | 3 | 3,911 | 116,630 | 3,635 | 76,986 | 1,519 | 37,931 |
| symbol_search | 3 | 111,312 | 443,710 | 1,808 | 85,295 | 17,244 | 86,093 |
| wavelet_encoded | 3 | 5,072 | 117,050 | 104 | 21,962 | 172 | 22,011 |
| **all** | 43 | 1,419,157 | 1,435,152 | 258,836 | 347,660 | 318,665 | 288,773 |

Geometry coverage: {"tasks": 1014, "real_geometry": 702, "surrogate_geometry": 619, "real_by_source": {"scratch_latest": 285, "scratch_original": 267, "return_cache_spanset": 78, "db": 72}, "surrogate_by_source": {"scratch_latest": 285, "scratch_original": 262, "db": 72}, "settings_whole_real": 77, "settings_whole_surrogate": 69, "by_recording": {"MJu26a_fs2": {"real": 498, "surrogate": 439, "tasks": 674}, "SH_fs2": {"real": 102, "surrogate": 90, "tasks": 170}, "SO_fs2": {"real": 102, "surrogate": 90, "tasks": 170}}}

| recording | channels | settings/channel (median) | real C median | shift mean | channels p<0.05 | surrogate settings | surrogate C median | real C same settings | bands real C (p) | bands surrogate C (p) |
|---|---:|---:|---:|---:|---:|---|---:|---:|---|---|
| MJu26a_fs2 | 16 | 31 | 0.17 | 0.00 | 16 | 26–31 | 0.02 | 0.17 | 0.15 (0.005) | 0.27 (0.005) |
| SH_fs2 | 4 | 24 | 0.26 | -0.00 | 4 | 21–26 | 0.02 | 0.31 | 0.09 (0.144) | 0.17 (0.005) |
| SO_fs2 | 4 | 26 | 0.24 | 0.00 | 4 | 22–23 | 0.03 | 0.29 | 0.38 (0.005) | 0.18 (0.005) |

| recording | geometry | settings | families | detections | candidates | 1-2 | 3-4 | 5-6 | 7-8 | 9+ |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| MJu26a_fs2 | real, all settings | 35 | 12 | 1,160,952 | 838,861 | 15.5 % | 48.3 % | 30.8 % | 5.1 % | 0.2 % |
| MJu26a_fs2 | real, surrogate's settings | 25 | 10 | 1,125,082 | 819,075 | 16.8 % | 51.7 % | 28.1 % | 3.4 % | 0.0 % |
| MJu26a_fs2 | surrogate | 25 | 10 | 763,793 | 641,957 | 12.6 % | 71.3 % | 15.8 % | 0.2 % | 0.0 % |
| SH_fs2 | real, all settings | 24 | 9 | 227,112 | 157,650 | 13.7 % | 62.1 % | 24.2 % | 0.0 % | 0.0 % |
| SH_fs2 | real, surrogate's settings | 20 | 7 | 199,477 | 136,119 | 21.7 % | 75.0 % | 3.2 % | 0.0 % | 0.0 % |
| SH_fs2 | surrogate | 20 | 7 | 44,208 | 33,855 | 46.3 % | 49.5 % | 4.2 % | 0.0 % | 0.0 % |
| SO_fs2 | real, all settings | 23 | 8 | 297,605 | 230,774 | 20.0 % | 52.0 % | 26.8 % | 1.2 % | 0.0 % |
| SO_fs2 | real, surrogate's settings | 20 | 7 | 274,420 | 213,772 | 31.2 % | 59.0 % | 9.7 % | 0.1 % | 0.0 % |
| SO_fs2 | surrogate | 20 | 7 | 77,162 | 67,648 | 40.3 % | 56.8 % | 2.8 % | 0.0 % | 0.0 % |

| Chapter 6 table | candidates | families | 1-2 | 3-4 | 5-6 | 7-8 | 9+ |
|---|---:|---:|---:|---:|---:|---:|---:|
| CO_fs2.mat | 229,807 | 13 | 18.7 % | 36.5 % | 27.6 % | 11.8 % | 5.4 % |
| L_LM_Jul_26_J_raw_fs2.mat | 616,299 | 13 | 11.4 % | 35.1 % | 30.8 % | 14.9 % | 7.7 % |
| LM_fs2.mat | 295,239 | 13 | 11.0 % | 31.3 % | 29.1 % | 18.7 % | 9.9 % |
| M2_aug_concat_fs1.mat | 1,502,319 | 13 | 6.4 % | 33.8 % | 32.4 % | 20.0 % | 7.4 % |
| M2_concat_fs1.mat | 455,907 | 12 | 15.7 % | 36.4 % | 26.2 % | 14.9 % | 6.8 % |
| M4_aug_concat_fs1.mat | 832,136 | 13 | 13.7 % | 48.6 % | 27.2 % | 6.8 % | 3.7 % |
| Schizophyllum commune.txt | 32,453 | 13 | 3.0 % | 35.2 % | 48.5 % | 13.1 % | 0.2 % |