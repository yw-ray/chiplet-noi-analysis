# Paper Positioning Notes: Workloads and Chiplet Topology

이 문서는 paper에서 4가지 핵심 질문에 명확히 답하기 위한 정리:
1. 우리가 쓰는 workload들이 어디서 왔는가
2. Base chiplet topology (mesh)는 실제 산업 제품인가
3. Express link은 누구의 제안인가
4. Reviewer 의심에 대한 방어 논리

## Workload origins (6개)

| Workload | NL% | 패턴 | 출처 | 논문 인용 |
|---|---|---|---|---|
| Tree All-Reduce | 42% | butterfly halving-doubling | NCCL/RCCL standard | Thakur 2005, NCCL tech ref |
| FSDP | 76% | TP-group dense + cross-group reduce | PyTorch FSDP, DeepSpeed ZeRO-3 | Rajbhandari'20 (ZeRO), PyTorch FSDP doc |
| Hybrid TP+PP | 77% | Megatron-LM TP=8 dense + PP edge | Megatron-LM | Shoeybi'19, Narayanan'21 |
| Uniform Random | 89% | all-pair uniform (synthetic) | worst-case baseline | (synthetic, no specific origin) |
| MoE Expert top-2 | 91% | Zipf(1.5) top-2 dispatch | DeepSeek-V3, Mixtral | Mixtral'24, DeepSeek-V3'24 |
| EP All-to-All | 92% | dense Zipf-weighted shuffle | DeepSeek-V3 EP | DeepSeek-V3'24 |

**중요 framing**: 6 workloads는 NL% spectrum (42~92)을 균등 분포로 cover. 각각 distinct connection pattern. Uniform은 synthetic worst-case로 명시.

## Base topology = 실제 산업 제품

| 시스템 | Chiplet 구조 | Year | Reference |
|---|---|---|---|
| AMD MI300X | 8 XCD + 4 IOD on interposer | 2024 | Hot Chips, `mi300x` |
| NVIDIA Blackwell (B200) | 2-die NVLink | 2024 | NVIDIA whitepaper, `blackwell` |
| Apple M2 Ultra (UltraFusion) | 2-die mesh | 2023 | WWDC23 |
| Intel Ponte Vecchio | 47 tiles EMIB | 2022 | ISSCC22 |
| TSMC CoWoS-S/L | Standard interposer | 2018+ | TSMC publications |

**Paper claim**: "Our 2.5D chiplet mesh substrate matches industry standards (MI300X, B200) — UCIe point-to-point D2D, CoWoS-class interposer wiring."

## Express links = academic proposal

| 논문 | 기여 | 우리 사용 |
|---|---|---|
| Kite (HPCA'20) | adjacent-only optimization (`kite_l/s/m`) | baseline |
| Florets (DAC'22) | row/column regular topology | FBfly motif baseline |
| GIA | adjacent + skip variant | `gia` baseline |
| NoC4Chiplet (TPDS'21) | non-adjacent link analysis | reference |
| PARL (arXiv'25) | RL-based NoI synthesis | closest related work |

**Paper claim**: "Non-adjacent express links are an academic proposal not yet in shipping products; we follow prior NoI literature (Kite, Florets, PARL) in studying their placement."

## 우리 contribution positioning

1. **Multi-workload superset**: Stage 1 MCTS finds topology that serves a workload mix (not single workload)
2. **Per-workload masking**: Stage 2 deactivates links per-workload to maximize specialization
3. **NL% predictor**: workload-level statistic that decides whether learned placement is worth invoking
4. **Both lat and EDP gains**: not just throughput, but energy-efficiency at iso-wire

## Reviewer 의심 대비

### Q: 왜 MI300X는 express link 안 쓰는가?
A: K=4-8 small system이라 mesh 거리 1-2 hop, phantom load 작음. K=16+ next-gen 시스템에서는 phantom load Θ(K^{3/2})로 증가 → express 필수. 우리 paper는 forward-looking K=16, 32 평가.

### Q: Wire는 어떻게 깔리는가? Physical feasibility?
A: CoWoS interposer는 3-6 metal layers 제공. 우리는 wire-area budget로 추상화 (실제 wire length × routing layer). Iso-wire budget으로 baseline과 fair comparison.

### Q: Workload가 production trace인가, synthetic인가?
A: Workload-inspired but synthetic. Tree (NCCL 알고리즘), FSDP (ZeRO-3 pattern), Hybrid (Megatron-LM TP+PP), MoE (DeepSeek/Mixtral Zipf), EP (DeepSeek-V3 EP), Uniform (synthetic worst-case). 각각의 dominant traffic shape를 모델링. End-to-end trace는 future work.

### Q: 왜 FSDP와 EP를 추가했나? (기존 4개로는 부족?)
A: FSDP는 2024-25 dominant training framework (PyTorch FSDP, DeepSpeed ZeRO-3). EP는 modern MoE production. 둘 다 우리 4개 워크로드 범위에서 cover되지 않은 distinct patterns. 따라서 추가는 "현재 LLM workload spectrum cover" claim 강화.

### Q: 우리 Hybrid TP+PP는 진짜 Megatron과 같은가?
A: 단순화됨. Steady-state TP-group dense + minimal PP edge만 모델링. Per-iteration micro-step dynamics(forward/backward separation)는 추상화. NoI placement decision에는 macro-level traffic shape이 dominant하므로 적절.

### Q: Uniform Random은 실 workload 아닌데 왜 넣었나?
A: Synthetic worst-case baseline. Adjacent-only allocator에게 가장 어려운 dense all-pair 패턴. Prior NoI literature (Kite, PARL evaluation set)에서도 표준 baseline으로 사용.

### Q: Inference workload는 왜 없나?
A: 본 paper는 training NoI 집중. Inference (KV-cache, prefill/decode 분리, speculative decoding)는 future work로 explicit하게 명시. Training은 chiplet system의 dominant computational regime.
