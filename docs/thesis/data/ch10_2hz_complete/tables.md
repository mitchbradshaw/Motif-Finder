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

Geometry coverage: {"tasks": 1014, "real_geometry": 1001, "surrogate_geometry": 979, "real_by_source": {"recomputed_pc": 299, "scratch_latest": 285, "scratch_original": 267, "return_cache_spanset": 78, "db": 72}, "surrogate_by_source": {"recomputed_pc": 360, "scratch_latest": 285, "scratch_original": 262, "db": 72}, "settings_whole_real": 122, "settings_whole_surrogate": 117, "by_recording": {"MJu26a_fs2": {"real": 664, "surrogate": 646, "tasks": 674}, "SH_fs2": {"real": 168, "surrogate": 165, "tasks": 170}, "SO_fs2": {"real": 169, "surrogate": 168, "tasks": 170}}}

| recording | channels | settings/channel (median) | real C median | shift mean | channels p<0.05 | surrogate settings | surrogate C median | real C same settings | bands real C (p) | bands surrogate C (p) |
|---|---:|---:|---:|---:|---:|---|---:|---:|---|---|
| MJu26a_fs2 | 16 | 42 | 0.21 | 0.00 | 16 | 38–42 | 0.02 | 0.22 | 0.14 (0.005) | 0.25 (0.005) |
| SH_fs2 | 4 | 42 | 0.26 | -0.00 | 4 | 40–42 | 0.02 | 0.27 | 0.07 (0.234) | 0.25 (0.005) |
| SO_fs2 | 4 | 42 | 0.27 | -0.00 | 4 | 41–43 | 0.02 | 0.27 | 0.41 (0.005) | 0.17 (0.005) |

| recording | geometry | settings | families | detections | candidates | 1-2 | 3-4 | 5-6 | 7-8 | 9+ |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| MJu26a_fs2 | real, all settings | 39 | 13 | 1,191,443 | 852,607 | 14.4 % | 39.8 % | 29.5 % | 10.9 % | 5.3 % |
| MJu26a_fs2 | real, surrogate's settings | 38 | 13 | 1,158,467 | 836,650 | 15.0 % | 41.4 % | 28.6 % | 10.9 % | 4.1 % |
| MJu26a_fs2 | surrogate | 38 | 13 | 923,027 | 788,691 | 9.7 % | 65.3 % | 23.4 % | 1.5 % | 0.1 % |
| SH_fs2 | real, all settings | 39 | 13 | 240,398 | 164,765 | 11.7 % | 38.2 % | 34.4 % | 12.2 % | 3.5 % |
| SH_fs2 | real, surrogate's settings | 36 | 13 | 226,859 | 154,888 | 11.0 % | 39.2 % | 33.8 % | 12.7 % | 3.3 % |
| SH_fs2 | surrogate | 36 | 13 | 227,014 | 203,168 | 7.7 % | 56.1 % | 32.5 % | 3.6 % | 0.1 % |
| SO_fs2 | real, all settings | 39 | 13 | 308,078 | 235,575 | 18.9 % | 39.5 % | 31.6 % | 8.0 % | 2.0 % |
| SO_fs2 | real, surrogate's settings | 34 | 13 | 305,409 | 235,023 | 19.2 % | 39.6 % | 31.6 % | 7.9 % | 1.7 % |
| SO_fs2 | surrogate | 34 | 13 | 206,111 | 180,105 | 8.2 % | 61.6 % | 27.3 % | 2.8 % | 0.1 % |

| recording | 5+ real (like for like) | 5+ surrogate | 7+ real (like for like) | 7+ surrogate | 7+ real, all settings | 9+ real, all settings |
|---|---:|---:|---:|---:|---:|---:|
| MJu26a_fs2 | 43.6 % | 25.0 % | 15.01 % | 1.60 % | 16.3 % | 5.30 % |
| SH_fs2 | 49.8 % | 36.2 % | 15.98 % | 3.68 % | 15.7 % | 3.47 % |
| SO_fs2 | 41.2 % | 30.2 % | 9.59 % | 2.90 % | 10.0 % | 1.99 % |

| recording | family | tasks | real geometry | surrogate geometry |
|---|---|---:|---:|---:|
| MJu26a_fs2 | BEADs_invert_detect_v1 | 48 | 44 | 43 |
| MJu26a_fs2 | Wavelet_detection_prototype | 48 | 48 | 36 |
| MJu26a_fs2 | cnn_1min | 64 | 58 | 53 |
| SH_fs2 | BEADs_invert_detect_v1 | 12 | 10 | 10 |
| SH_fs2 | Wavelet_detection_prototype | 12 | 12 | 9 |
| SO_fs2 | BEADs_invert_detect_v1 | 12 | 11 | 11 |
| SO_fs2 | Wavelet_detection_prototype | 12 | 12 | 11 |

| Chapter 6 table | candidates | families | 1-2 | 3-4 | 5-6 | 7-8 | 9+ |
|---|---:|---:|---:|---:|---:|---:|---:|
| CO_fs2.mat | 229,807 | 13 | 18.7 % | 36.5 % | 27.6 % | 11.8 % | 5.4 % |
| L_LM_Jul_26_J_raw_fs2.mat | 616,299 | 13 | 11.4 % | 35.1 % | 30.8 % | 14.9 % | 7.7 % |
| LM_fs2.mat | 295,239 | 13 | 11.0 % | 31.3 % | 29.1 % | 18.7 % | 9.9 % |
| M2_aug_concat_fs1.mat | 1,502,319 | 13 | 6.4 % | 33.8 % | 32.4 % | 20.0 % | 7.4 % |
| M2_concat_fs1.mat | 455,907 | 12 | 15.7 % | 36.4 % | 26.2 % | 14.9 % | 6.8 % |
| M4_aug_concat_fs1.mat | 832,136 | 13 | 13.7 % | 48.6 % | 27.2 % | 6.8 % | 3.7 % |
| Schizophyllum commune.txt | 32,453 | 13 | 3.0 % | 35.2 % | 48.5 % | 13.1 % | 0.2 % |