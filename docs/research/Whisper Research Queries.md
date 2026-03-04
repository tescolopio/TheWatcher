# **Technical Evaluation of Whisper Transcription Backends and Optimization for Complex Narrative Environments**

The evolution of automatic speech recognition (ASR) has reached a critical juncture with the introduction of OpenAI’s Whisper model. By leveraging a massive dataset of 680,000 hours of multilingual and multitask supervised data, Whisper has redefined the performance floor for generalized speech-to-text systems.1 Unlike traditional models that required bespoke fine-tuning to perform reliably in specific acoustic contexts, Whisper demonstrates an inherent robustness to diverse accents, background noise, and technical jargon.2 This capacity for zero-shot generalization is particularly relevant for high-complexity narrative environments, such as Tabletop Role-Playing Game (TTRPG) sessions, where the mixture of simultaneous speakers, theatrical character voices, and invented proper nouns presents a formidable challenge to conventional ASR architectures.5

## **Architectural Foundations of the Whisper Model**

The fundamental design of Whisper is based on an encoder-decoder Transformer architecture, which is a standard for modern sequence-to-sequence tasks.1 The processing pipeline begins with a series of preprocessing steps that convert raw audio data into a time-frequency representation known as a log-Mel spectrogram.1 This representation maps the signal frequencies to the Mel scale, effectively mirroring the frequency sensitivity of human auditory perception and providing a biologically grounded feature set for the neural network.1

The model architecture utilizes a convolutional front-end that processes the spectrogram before passing the resulting vectors into the Transformer encoder. The encoder transforms these inputs into a sequence of latent representations that capture both spectral characteristics and temporal dynamics.9 The decoder then generates text tokens sequentially, guided by both the encoder’s output and the context of previously generated tokens.9 This multitasking approach is mediated through the use of special tokens within the decoder, which instruct the model to perform specific tasks such as language identification, translation into English, or generating phrase-level timestamps.3

Whisper is available in multiple configurations, varying by parameter count and intended use case. These versions—tiny, base, small, medium, and large—allow developers to balance the trade-off between transcription accuracy and computational resource requirements.1

| Model Variant | Parameters | PyTorch Weights (.pt) | GGML Q5 Quantized | Published English WER |
| :---- | :---- | :---- | :---- | :---- |
| tiny | 39 Million | 75 MB | 32 MB | \~7.7% |
| base | 74 Million | 142 MB | 60 MB | \~5.7% |
| small | 244 Million | 466 MB | 190 MB | \~3.4% |
| medium | 769 Million | 1.5 GB | 515 MB | \~2.1% |
| large-v3 | 1.55 Billion | 3.1 GB | 1.1 GB | \~1.8% |

Note: The Word Error Rate (WER) metrics provided in the table represent ideal performance on clean datasets such as LibriSpeech.10 In narrative environments like TTRPGs, actual WER is expected to be higher due to domain-specific linguistic and acoustic variables.6

## **Comparative Analysis of High-Performance Backends**

While the original OpenAI implementation provides a reference for accuracy, several optimized backends have emerged to address the speed and memory limitations of the Python-based PyTorch runtime.11 The most significant of these for local deployment are openai-whisper, whisper.cpp, and faster-whisper.

### **The Pythonic Reference: openai-whisper**

The openai-whisper package utilizes the standard PyTorch framework and serves as the baseline for all performance comparisons. While it is the most straightforward implementation to install and maintain, it faces scalability challenges when processing long-form audio.1 The backend processes audio in fixed 30-second chunks, which can lead to high wall-clock times if the hardware cannot support rapid sequential processing.2 Furthermore, Python's Global Interpreter Lock (GIL) and the overhead of the PyTorch runtime often lead to higher peak memory usage compared to low-level C++ implementations.12

### **Low-Level Efficiency: whisper.cpp**

Developed as a C/C++ port of Whisper, whisper.cpp is optimized for high-performance inference on local hardware without the need for external dependencies.10 A primary technical advantage of whisper.cpp is its "zero runtime allocation" philosophy, which eliminates memory fragmentation and overhead during the inference process.10 This backend is specifically tailored for CPU-based inference, supporting AVX intrinsics for x86 architectures and NEON/Accelerate for ARM-based systems like Apple Silicon.13

On Apple Silicon hardware, whisper.cpp can offload encoder inference to the Apple Neural Engine (ANE) via Core ML, achieving a significant speedup compared to CPU-only execution.14 Recent updates (v1.8.3) have introduced robust Vulkan support, enabling a 12-fold performance increase for systems utilizing integrated graphics from AMD and Intel.16

### **Parallel Inference and Scaling: faster-whisper**

The faster-whisper implementation is a reimplementation of the model using CTranslate2, a C++ engine designed for efficient Transformer inference.11 This backend focuses on massive throughput by utilizing weight quantization (e.g., INT8, FP16) and architectural optimizations like layer fusion and padding removal.11 A defining feature of faster-whisper is its support for batched inference, allowing multiple audio segments to be processed simultaneously on the GPU.1

Evidence suggests that while whisper.cpp is highly effective for short clips or CPU-bound environments, faster-whisper demonstrates superior scaling for longer recordings.15 In comparative benchmarks involving a 31-second audio sample, faster-whisper (base) completed the task in 5.07 seconds, whereas whisper.cpp (base) required 49.15 seconds.15 This indicates that CTranslate2 has better internal mechanisms for sequence chunking and memory management as audio length increases.15

## **Hardware-Specific Benchmarking and RTFx Analysis**

Selecting the optimal backend depends heavily on the available hardware. The Real-Time Factor (RTFx), representing the ratio of audio duration to transcription time, is the primary metric for assessing efficiency.20

### **High-End GPU Performance**

Modern discrete GPUs provide an order of magnitude increase in throughput. High-end NVIDIA cards, such as the RTX 4090, can transcribe audio at speeds exceeding 3,000 words per minute.21 On these systems, the large-v3 model can be processed at a rate far exceeding real-time.22 Specialized APIs, such as the Fireworks Audio API, have reported the ability to transcribe one hour of audio in as little as four seconds using optimized GPU clusters.23

| Hardware Platform | Backend Used | Model Size | RTFx (Approximate) | Performance Metric |
| :---- | :---- | :---- | :---- | :---- |
| RTX 4090 (24GB) | TensorRT-LLM | large-v3 | 27.0x | 1-hr audio in 2.2 min |
| RTX 3090 (24GB) | faster-whisper | large-v2 | 17.0x | 1-hr audio in 3.5 min |
| RTX 2080 Ti (11GB) | openai-whisper | medium | 5.0x \- 8.0x | Competitive local option |
| Apple M2 Pro (32GB) | whisper.cpp (ANE) | base | 18.0x | 30-min meeting in 100s |
| Intel N97 (4-core) | whisper.cpp (CPU) | tiny | 1.8x \- 2.0x | Edge device baseline |

### **CPU and Integrated Graphics Efficiency**

For environments restricted to CPU inference, whisper.cpp remains the dominant choice. Modern CPUs with parallelization can achieve faster-than-real-time performance for the base and tiny models.24 On Raspberry Pi 5 hardware, the tiny model can be run at approximately real-time speeds, making it a viable floor for low-power deployments.25

The introduction of Vulkan-based iGPU support in whisper.cpp 1.8.3 represents a significant milestone for "GPU poor" users.16 By leveraging the integrated Radeon 680M or Intel Arc graphics, users can achieve a three-to-four-fold improvement in RTFx compared to CPU-only processing on the same silicon.16 This represents a total 12x speedup in some scenarios, moving large-model transcription closer to the realm of feasibility on standard corporate laptops.16

## **Memory Management and Constraints in Long-Form Transcription**

The resident set size (RSS) of the transcription process is a critical variable, particularly on hardware with 8GB of RAM. Memory consumption is influenced by the static model weights, the inference engine overhead, and the dynamic allocation required for the audio waveform and its corresponding attention maps.26

### **Static and Dynamic RAM Requirements**

The memory footprint for Whisper starts at approximately 125 MB for the tiny model and scales exponentially with model complexity.10

| Model | Reported Memory Footprint (RSS) | Minimum VRAM (GPU) | Recommended RAM (CPU) |
| :---- | :---- | :---- | :---- |
| tiny | \~125 MB | 1 GB | 2 GB |
| base | \~210 MB | 1 GB | 2 GB |
| small | \~600 MB | 2 GB | 4 GB |
| medium | \~1.7 GB | 5 GB | 8 GB |
| large-v3 | \~3.3 GB | 10 GB | 16 GB |

While these figures represent the model weights, actual execution requires additional buffer space. In PyTorch-based environments, the waveform tensor itself must be resident in memory, and the cross-attention layers utilized during decoding can rapidly consume available RAM.28

### **The Long Audio Memory Bottleneck**

Transcription of sessions lasting multiple hours (e.g., a 3-hour RPG recording) introduces significant memory pressure. Research indicates that memory usage can explode when computing word-level timestamps, as the system must track complex attention weights across the entire sequence.28 In one test case, transcribing an 81-minute audio file with the large-v3 model on a CPU allocated up to 50 GB of system RAM, likely due to a memory leak in the cross-attention weight tracking mechanism of the transformers library.28

On systems with 8GB of RAM, the medium model is the theoretical limit, but in practice, long audio durations often trigger out-of-memory (OOM) errors or force the system into aggressive disk swapping.29 For stable 3-hour sessions on 8GB hardware, the small model is the recommended maximum to ensure sufficient headroom for the operating system and other concurrent bot tasks.29

### **Mitigation Strategies for OOM Events**

To process lengthy recordings on constrained hardware, several technical mitigations are necessary:

1. **Preprocessing via Chunking:** Breaking the audio into 10-20 minute segments before passing it to the ASR model prevents the accumulation of massive attention tensors.27  
2. **Integer Quantization:** Utilizing 4-bit (INT4) or 5-bit (INT5) quantized models reduces the resident weight size by up to 69%, significantly lowering the memory baseline.32  
3. **VAD Pre-filtering:** Employing an external Voice Activity Detection (VAD) model to strip silent segments before transcription reduces the total token count and computational load.12

## **Challenges in Narrative ASR: Accents, Crosstalk, and Jargon**

Transcribing narrative content such as TTRPG sessions requires the model to navigate linguistic complexities that are absent from standardized benchmarks like LibriSpeech.

### **Accent Sensitivity and Regional Dialects**

Whisper demonstrates a significant performance discrepancy between native and non-native English speakers.5 In studies of accented speech, error rates were consistently higher for non-native groups, with the baseline model showing particular sensitivity to variations in prosody and vowel elongation.5 Multilingual models typically generalize better to these underrepresented accents than English-only variants due to the diverse phonetic exposure during training.35

In the context of TTRPGs, where players often adopt specific character accents (e.g., pseudo-European or regional dialects), phonetic misidentification is common. A model may misread a theatrical "bored" as "bald" or fail to differentiate between subtle vowel shifts in fantasy terminology.36

### **The Fictional Proper Noun Problem**

Invented proper nouns—such as "Theron Ashveil" or "Cambuslang"—represent a systematic failure mode for out-of-the-box Whisper models.6 Because these terms do not exist in the training corpus, the model frequently attempts to map them to the nearest real-world homophone.6 This leads to transcripts that are syntactically correct but narratively nonsensical.32

Furthermore, different speakers within a session may adopt varying pronunciations for the same fantasy term, creating a high level of acoustic entropy that degrades the model's confidence in its predictions.6

### **Simultaneous Speech and Hallucination**

The social nature of gaming sessions leads to frequent crosstalk. sequential decoding algorithms often fail during these segments, either skipping the audio entirely or generating "hallucinations"—text that appears plausible but is not present in the signal.12 Whisper is also known to hallucinate when processing long silent periods or pure background noise, sometimes inserting non-existent references to race, violence, or medication.8 This behavior can be addressed by using external VAD to ensure the model only processes segments containing valid speech.33

## **Strategic Preprocessing and the initial\_prompt Mechanism**

To maximize the quality of TTRPG transcriptions, developers can utilize Whisper’s built-in biasing features and external audio manipulation tools.

### **Optimization through ffmpeg Pre-resampling**

Whisper is natively optimized for 16 kHz mono audio. While backends like openai-whisper and whisper.cpp can resample Discord’s 48 kHz stereo signal internally, this often involves spinning up a subprocess that may not be as efficient as a dedicated preprocessing step.38

| Audio Parameter | Recommended Setting | Technical Justification |
| :---- | :---- | :---- |
| Channels | Mono (1) | Stereo provides no additional data for transcription and doubles size.39 |
| Sample Rate | 16,000 Hz | Native rate; prevents internal transcoding overhead.39 |
| Bitrate | 32-64 kbps | Transcription accuracy remains stable even at low bitrates.39 |
| Bit Depth | 16-bit | Standard for speech; required by many C++ binary versions.13 |

Evidence suggests that pre-resampling with a high-quality library like soxr (included in ffmpeg) ensures that the audio quality is preserved while minimizing the computational burden on the ASR engine.39 A standardized preprocessing command for a TTRPG session recording would be: ffmpeg \-i session\_audio.wav \-ar 16000 \-ac 1 \-c:a pcm\_s16le session\_prepared.wav.14

### **Lexical Biasing via initial\_prompt**

The initial\_prompt is a specialized parameter that prepends text to the decoder’s context, effectively "priming" the model to expect specific vocabulary or styles.43 Unlike an LLM prompt that allows for complex instructions, the Whisper prompt is a tool for lexical bias.43

Key constraints of the initial\_prompt:

* **Context Window:** The decoder only considers the last ![][image1] tokens of the prompt; any content beyond this limit is ignored.43  
* **Recency Bias:** Tokens placed at the end of the prompt exert significantly more influence than those at the beginning.43  
* **Style matching:** If the prompt is formatted as a lowercase word list, the resulting transcript will often adopt that style.44

For a narrative session, the prompt should be dynamically generated to include the current character names and active plot locations, ensuring that the model prioritizes these rare tokens during the decoding process.43 Research into multi-agent pipelines has shown that using an LLM to generate these prompts from a first-pass transcript can reduce WER by up to 17% without retraining the Whisper model itself.43

## **Software Engineering and Systemic Integration**

Implementing these backends within a production bot requires addressing breaking changes in the software ecosystem and the complexities of real-time audio capture.

### **whisper.cpp Binary and CLI Conventions**

A critical deployment hurdle is the 2024 renaming of the whisper.cpp binaries. Executables previously known as main and server have been changed to whisper-cli and whisper-server respectively to prevent naming conflicts with standard system utilities.46

| Component | Current Binary Name | Milestones |
| :---- | :---- | :---- |
| Transcription CLI | whisper-cli | Primary tool for file-based transcription.47 |
| Local Server | whisper-server | Provides an HTTP interface for ASR.47 |
| Benchmark Tool | whisper-bench | Measures performance on local silicon.46 |
| Real-time Stream | whisper-stream | Requires SDL2 for microphone/capture support.46 |

Systems like "TheWatcher" must handle fallback logic to detect if a user has configured an older binary version or a newer CLI standard.49 Furthermore, when calling these binaries via a Python subprocess, the \--output-txt \- flag is standard for reading the result from stdout.14 It is vital to use the \--no-timestamps or \-nt flag if the raw text is required without segment prefixes, as stdout historically included bracketed time ranges by default.14

### **Discord Audio Capture via Pycord Sinks**

Capturing multi-user audio for transcription involves the use of "sinks" within the py-cord or discord.py frameworks.54 Discord audio is delivered via UDP in Opus-encoded packets. To prepare this data for Whisper, a WaveSink or PCMSink must decode these packets into 48 kHz stereo PCM bytes.54

Common pitfalls in sink implementation include:

1. **Buffer Management:** Failing to seek(0) the internal BytesIO buffer after recording is complete results in read operations returning empty data.58  
2. **Temporal Alignment:** Standard sinks do not record silence when a user is not speaking. In a multi-user recording, this leads to a complete loss of synchronization between participants.59  
3. **Sync Start:** The sync\_start=True parameter in the start\_recording method is essential for ensuring that all user tracks are temporally aligned to the beginning of the session recording, effectively padding gaps with digital silence.60

## **Downstream Processing: Synthesis and Summarization**

The raw transcript generated by Whisper is rarely the end-product; it usually serves as input for a Large Language Model (LLM) to perform summarization or entity extraction.5

### **Local LLM Benchmarks for Narrative Synthesis**

When summarizing a session, the model must maintain entity preservation—remembering that "Theron" is the Paladin and not a geographical location.

| Model Variant | Context Window | Relative Performance | Primary Advantage |
| :---- | :---- | :---- | :---- |
| Llama 3.1 8B | 128k tokens | High General Knowledge | Strong dialogue understanding.62 |
| Mistral v0.3 7B | 32k tokens | Optimized for Speed | Low-latency instruction following.64 |
| Qwen 2.5 7B | 128k tokens | Superior in Jargon | High precision in structured extraction.66 |
| Gemma 2 9B | 8k tokens | Highly Aligned | Consistent formatting for reports.64 |

Llama 3.1 8B is widely regarded as the best "all-rounder" for general dialogue flows, whereas Qwen 2.5 has surpassed Llama in specialized tasks involving code and structured data.62

### **The Context Window and Silent Truncation Risks**

A recurring issue in local LLM deployment via Ollama is the "context window fallacy".67 While a model like Llama 3.1 supports 128k tokens, Ollama defaults to a 4,096-token context window for all models unless explicitly configured otherwise.67 When a 3-hour transcript exceeds this 4k limit, the system performs "silent truncation," dropping the oldest tokens from the front of the sequence.71

This leads to a phenomenon known as "model amnesia," where the LLM forgets the session introduction or initial character cards.68 Developers must explicitly set the OLLAMA\_CONTEXT\_LENGTH environment variable or the num\_ctx parameter in the API call to utilize the model’s full architectural capacity.67

## **Emerging Trends and Technical Outlook**

The field of automatic speech recognition is moving toward natively multimodal architectures. Future versions of Gemini (2.0) and GPT-4o are capable of processing raw audio features directly, bypassing the need for a discrete text transcript.8 This approach allows the model to perceive acoustic nuances such as sarcasm, intensity, and ambient emotional tone that are inherently lost in the current Whisper-then-LLM pipeline.34

Furthermore, projects like Distil-Whisper are significantly reducing the computational cost of high-quality ASR. By training smaller "student" models to mimic the large-v3 encoder, developers have produced models that are up to 6 times faster while maintaining a Word Error Rate within 1% of the original billion-parameter version.1

## **Conclusion and Strategic Technical Path**

The successful deployment of a transcription system for complex narrative sessions requires a multi-layered technical strategy that accounts for backend efficiency, acoustic complexity, and memory management.

1. **Backend Strategy:** Implement a dual-backend system that defaults to whisper.cpp for CPU-intensive local tasks—taking advantage of its zero-allocation memory model and iGPU acceleration—while providing a fallback to faster-whisper for long-form, multi-hour sessions where GPU batching can be leveraged.  
2. **Acoustic Optimization:** Mandatory preprocessing of Discord audio to 16 kHz mono using external ffmpeg libraries ensures that the ASR engine operates at its native efficiency peak.  
3. **Linguistic Biasing:** Utilize a dynamically updated initial\_prompt containing current character names and fictional proper nouns to overcome the phonetic ambiguity inherent in fantasy settings.  
4. **Memory Resilience:** For hardware with 8GB of RAM, the small model should be the production default for multi-hour sessions to prevent OOM-induced system crashes, with medium reserved for high-priority, high-resource environments.  
5. **Synthesis Integrity:** Local LLM summarization must be configured with explicit context window management (num\_ctx) and JSON schema enforcement to ensure consistent and narratively accurate session records.

As the industry moves toward multimodal reasoning, the current separation between speech recognition and text analysis will eventually merge. Until that transition is complete, the integration of optimized C++ backends with dynamic lexical biasing remains the most robust solution for transcribing the complex, creative narratives generated at the modern gaming table.

#### **Works cited**

1. Whisper Variants Comparison: What Are Their Features And How To Implement Them?, accessed March 4, 2026, [https://towardsai.net/p/machine-learning/whisper-variants-comparison-what-are-their-features-and-how-to-implement-them](https://towardsai.net/p/machine-learning/whisper-variants-comparison-what-are-their-features-and-how-to-implement-them)  
2. Whisper : A multilingual and multitask robust ASR model | Shaped, accessed March 4, 2026, [https://www.shaped.ai/blog/whisper-a-multilingual-and-multitask-robust-asr-model](https://www.shaped.ai/blog/whisper-a-multilingual-and-multitask-robust-asr-model)  
3. Introducing Whisper \- OpenAI, accessed March 4, 2026, [https://openai.com/index/whisper/](https://openai.com/index/whisper/)  
4. Whisper, A Breakthrough in Speech-Recognition AI | by ENERZAi \- Medium, accessed March 4, 2026, [https://medium.com/@enerzai/whisper-a-breakthrough-in-speech-recognition-ai-007aa5abf736](https://medium.com/@enerzai/whisper-a-breakthrough-in-speech-recognition-ai-007aa5abf736)  
5. Accents Still Confuse AI: Systematic Errors in Speech Transcription and LLM-Based Remedies | medRxiv, accessed March 4, 2026, [https://www.medrxiv.org/content/10.1101/2025.08.29.25333548v1.full-text](https://www.medrxiv.org/content/10.1101/2025.08.29.25333548v1.full-text)  
6. Effectiveness of Whisper's Fine-Tuning for Domain-Specific Use Cases in the Industry \- Fraunhofer-Publica, accessed March 4, 2026, [https://publica.fraunhofer.de/bitstreams/77ba042a-7869-40d3-b780-920d606eb18c/download](https://publica.fraunhofer.de/bitstreams/77ba042a-7869-40d3-b780-920d606eb18c/download)  
7. Effectiveness of Whisper's Fine-Tuning for Domain-Specific Use Cases in the Industry \- SciTePress, accessed March 4, 2026, [https://www.scitepress.org/Papers/2025/133781/133781.pdf](https://www.scitepress.org/Papers/2025/133781/133781.pdf)  
8. Whisper (speech recognition system) \- Wikipedia, accessed March 4, 2026, [https://en.wikipedia.org/wiki/Whisper\_(speech\_recognition\_system)](https://en.wikipedia.org/wiki/Whisper_\(speech_recognition_system\))  
9. Whisper, A Breakthrough in Speech-Recognition AI \- ENERZAi, accessed March 4, 2026, [https://enerzai.com/ko/resources/blog/whisper-a-breakthrough-in-speech-recognition-ai](https://enerzai.com/ko/resources/blog/whisper-a-breakthrough-in-speech-recognition-ai)  
10. RubyDoc.info: File: README – Documentation for whispercpp (1.3.0), accessed March 4, 2026, [https://www.rubydoc.info/gems/whispercpp/1.3.0](https://www.rubydoc.info/gems/whispercpp/1.3.0)  
11. Choosing between Whisper variants: faster-whisper, insanely-fast-whisper, WhisperX, accessed March 4, 2026, [https://modal.com/blog/choosing-whisper-variants](https://modal.com/blog/choosing-whisper-variants)  
12. Generally Available: The fastest, most accurate and cost-efficient Whisper transcription, accessed March 4, 2026, [https://www.baseten.co/blog/the-fastest-most-accurate-and-cost-efficient-whisper-transcription/](https://www.baseten.co/blog/the-fastest-most-accurate-and-cost-efficient-whisper-transcription/)  
13. Install whisper.cpp (UNOFFICIAL) on Linux | Snap Store \- Snapcraft, accessed March 4, 2026, [https://snapcraft.io/whisper-cpp](https://snapcraft.io/whisper-cpp)  
14. ggml-org/whisper.cpp: Port of OpenAI's Whisper model in C/C++ \- GitHub, accessed March 4, 2026, [https://github.com/ggml-org/whisper.cpp](https://github.com/ggml-org/whisper.cpp)  
15. Performance Question: whisper.cpp vs faster-whisper scaling on longer audio \- am I missing optimizations? · Issue \#3682 · ggml-org/whisper.cpp \- GitHub, accessed March 4, 2026, [https://github.com/ggml-org/whisper.cpp/issues/3682](https://github.com/ggml-org/whisper.cpp/issues/3682)  
16. Whisper.cpp 1.8.3 Delivers A "12x Performance Boost" With Integrated Graphics \- Phoronix, accessed March 4, 2026, [https://www.phoronix.com/news/Whisper-cpp-1.8.3-12x-Perf](https://www.phoronix.com/news/Whisper-cpp-1.8.3-12x-Perf)  
17. Speeding up Whisper \- Mobius Labs, accessed March 4, 2026, [https://mobiusml.github.io/batched\_whisper\_blog/](https://mobiusml.github.io/batched_whisper_blog/)  
18. faster-whisper \- PyPI, accessed March 4, 2026, [https://pypi.org/project/faster-whisper/](https://pypi.org/project/faster-whisper/)  
19. faster-whisper can be faster in many cases, even on CPU. \- Hacker News, accessed March 4, 2026, [https://news.ycombinator.com/item?id=46557573](https://news.ycombinator.com/item?id=46557573)  
20. The Top Open Source Speech-to-Text (STT) Models in 2025 \- Modal, accessed March 4, 2026, [https://modal.com/blog/open-source-stt](https://modal.com/blog/open-source-stt)  
21. OpenAI Whisper Audio Transcription Benchmarked on 18 GPUs \- Tom's Hardware, accessed March 4, 2026, [https://www.tomshardware.com/news/whisper-audio-transcription-gpus-benchmarked](https://www.tomshardware.com/news/whisper-audio-transcription-gpus-benchmarked)  
22. Yes, for my demo I am using whisper.cpp however there is an implementation tha... | Hacker News, accessed March 4, 2026, [https://news.ycombinator.com/item?id=36577580](https://news.ycombinator.com/item?id=36577580)  
23. 20x faster Whisper than OpenAI \- Fireworks audio transcribes 1 hour in 4 seconds, accessed March 4, 2026, [https://fireworks.ai/blog/audio-transcription-launch](https://fireworks.ai/blog/audio-transcription-launch)  
24. We've been researching different speech models at Scrimba, and went for Whisper ... \- Hacker News, accessed March 4, 2026, [https://news.ycombinator.com/item?id=35367655](https://news.ycombinator.com/item?id=35367655)  
25. Is Whisper.cpp still the king of STT? : r/LocalLLaMA \- Reddit, accessed March 4, 2026, [https://www.reddit.com/r/LocalLLaMA/comments/1hc1qzi/is\_whispercpp\_still\_the\_king\_of\_stt/](https://www.reddit.com/r/LocalLLaMA/comments/1hc1qzi/is_whispercpp_still_the_king_of_stt/)  
26. Memory requirements? · openai whisper · Discussion \#5 \- GitHub, accessed March 4, 2026, [https://github.com/openai/whisper/discussions/5](https://github.com/openai/whisper/discussions/5)  
27. OpenAI Whisper Transcription Out of Memory Error \- Help \- Pipedream, accessed March 4, 2026, [https://pipedream.com/community/t/openai-whisper-transcription-out-of-memory-error/5404](https://pipedream.com/community/t/openai-whisper-transcription-out-of-memory-error/5404)  
28. Whisper v-3 pipeline requiring a lot of memory when setting return\_timestamps="word" · Issue \#27834 · huggingface/transformers \- GitHub, accessed March 4, 2026, [https://github.com/huggingface/transformers/issues/27834](https://github.com/huggingface/transformers/issues/27834)  
29. faster-whisper vs whisper.cpp with CoreML \#368 \- GitHub, accessed March 4, 2026, [https://github.com/SYSTRAN/faster-whisper/discussions/368](https://github.com/SYSTRAN/faster-whisper/discussions/368)  
30. Best strategy on managing concurrent calls ? (Python/Asyncio) \- API, accessed March 4, 2026, [https://community.openai.com/t/best-strategy-on-managing-concurrent-calls-python-asyncio/849702](https://community.openai.com/t/best-strategy-on-managing-concurrent-calls-python-asyncio/849702)  
31. Whisper: Maximum content size limit exceeded \- API \- OpenAI Developer Community, accessed March 4, 2026, [https://community.openai.com/t/whisper-maximum-content-size-limit-exceeded/83925](https://community.openai.com/t/whisper-maximum-content-size-limit-exceeded/83925)  
32. Quantization for OpenAI's Whisper Models: A Comparative Analysis \- arXiv, accessed March 4, 2026, [https://arxiv.org/html/2503.09905v1](https://arxiv.org/html/2503.09905v1)  
33. OpenAI Whisper: Multilingual ASR \- Emergent Mind, accessed March 4, 2026, [https://www.emergentmind.com/topics/openai-whisper](https://www.emergentmind.com/topics/openai-whisper)  
34. How WhisperAI Uses OpenAI Whisper for 99% Accuracy, accessed March 4, 2026, [https://whisperai.com/blog/whisper-ai-accuracy](https://whisperai.com/blog/whisper-ai-accuracy)  
35. How biased is Whisper ? Evaluating Whisper Models for Robustness to Diverse English Accents \- Hugging Face, accessed March 4, 2026, [https://huggingface.co/blog/Steveeeeeeen/how-biaised-is-whisper](https://huggingface.co/blog/Steveeeeeeen/how-biaised-is-whisper)  
36. Adapting Whisper for Regional Dialects: Enhancing Public Services for Vulnerable Populations in the United Kingdom \- arXiv, accessed March 4, 2026, [https://arxiv.org/html/2501.08502v1](https://arxiv.org/html/2501.08502v1)  
37. Whisper leaves out chunks of speech in longer transcript \- OpenAI Developer Community, accessed March 4, 2026, [https://community.openai.com/t/whisper-leaves-out-chunks-of-speech-in-longer-transcript/715999](https://community.openai.com/t/whisper-leaves-out-chunks-of-speech-in-longer-transcript/715999)  
38. Optimal sample rate for input audio? · openai whisper · Discussion \#870 \- GitHub, accessed March 4, 2026, [https://github.com/openai/whisper/discussions/870](https://github.com/openai/whisper/discussions/870)  
39. Optimal Audio Input Settings for OpenAI Whisper Speech-to-Text \- Gist \- GitHub, accessed March 4, 2026, [https://gist.github.com/danielrosehill/06fb17e7462980f99efa9fdab2335a14](https://gist.github.com/danielrosehill/06fb17e7462980f99efa9fdab2335a14)  
40. Optimise OpenAI Whisper API: Audio Format, Sampling Rate and Quality \- DEV Community, accessed March 4, 2026, [https://dev.to/mxro/optimise-openai-whisper-api-audio-format-sampling-rate-and-quality-29fj](https://dev.to/mxro/optimise-openai-whisper-api-audio-format-sampling-rate-and-quality-29fj)  
41. From Go Code to Homebrew Tap: Writing and Deploying a Whisper CLI with GoReleaser, accessed March 4, 2026, [https://appliedgo.net/whisper-cli/](https://appliedgo.net/whisper-cli/)  
42. How good is ffmpeg downsampling? : r/linuxaudio \- Reddit, accessed March 4, 2026, [https://www.reddit.com/r/linuxaudio/comments/1eyac4i/how\_good\_is\_ffmpeg\_downsampling/](https://www.reddit.com/r/linuxaudio/comments/1eyac4i/how_good_is_ffmpeg_downsampling/)  
43. Final Project Report Whisper: Courtside Edition \- arXiv.org, accessed March 4, 2026, [https://arxiv.org/html/2602.18966v1](https://arxiv.org/html/2602.18966v1)  
44. Whisper prompting guide \- OpenAI for developers, accessed March 4, 2026, [https://developers.openai.com/cookbook/examples/whisper\_prompting\_guide/](https://developers.openai.com/cookbook/examples/whisper_prompting_guide/)  
45. Addressing transcription misspellings: prompt vs post-processing \- OpenAI for developers, accessed March 4, 2026, [https://developers.openai.com/cookbook/examples/whisper\_correct\_misspelling/](https://developers.openai.com/cookbook/examples/whisper_correct_misspelling/)  
46. Renamed binaries \#2780 \- ggml-org whisper.cpp \- GitHub, accessed March 4, 2026, [https://github.com/ggerganov/whisper.cpp/discussions/2780](https://github.com/ggerganov/whisper.cpp/discussions/2780)  
47. examples/deprecation-warning/README.md · natasa365/whisper.cpp at 46e7c8765e48803c7186f39530e2ed090ed3bd2a \- Hugging Face, accessed March 4, 2026, [https://huggingface.co/spaces/natasa365/whisper.cpp/blob/46e7c8765e48803c7186f39530e2ed090ed3bd2a/examples/deprecation-warning/README.md](https://huggingface.co/spaces/natasa365/whisper.cpp/blob/46e7c8765e48803c7186f39530e2ed090ed3bd2a/examples/deprecation-warning/README.md)  
48. Outdated Documentation and Deprecation Conflicts in whisper.cpp Examples \[whisper-stream, whisper-command does not exist\] · Issue \#2722 · ggml-org/whisper.cpp \- GitHub, accessed March 4, 2026, [https://github.com/ggerganov/whisper.cpp/issues/2722](https://github.com/ggerganov/whisper.cpp/issues/2722)  
49. \`main\` binary deprecated · Issue \#3 · rhasspy/wyoming-whisper-cpp \- GitHub, accessed March 4, 2026, [https://github.com/rhasspy/wyoming-whisper-cpp/issues/3](https://github.com/rhasspy/wyoming-whisper-cpp/issues/3)  
50. Generating Timestamp Information via whisper.cpp Server \#1875 \- GitHub, accessed March 4, 2026, [https://github.com/ggerganov/whisper.cpp/discussions/1875](https://github.com/ggerganov/whisper.cpp/discussions/1875)  
51. Transcribing MP3s with whisper-cpp on macOS \- Simon Willison: TIL, accessed March 4, 2026, [https://til.simonwillison.net/macos/whisper-cpp](https://til.simonwillison.net/macos/whisper-cpp)  
52. Transcribe any media using whisper-cli and ffmpeg \- GitHub Gist, accessed March 4, 2026, [https://gist.github.com/GammelSami/e1e895a42d036d28dd6286df5b3fbb81](https://gist.github.com/GammelSami/e1e895a42d036d28dd6286df5b3fbb81)  
53. WhisperFile \- extremely easy whisper.cpp audio transcription in one file : r/LocalLLaMA, accessed March 4, 2026, [https://www.reddit.com/r/LocalLLaMA/comments/1ewgb1f/whisperfile\_extremely\_easy\_whispercpp\_audio/](https://www.reddit.com/r/LocalLLaMA/comments/1ewgb1f/whisperfile_extremely_easy_whispercpp_audio/)  
54. discord-ext-voice-recv \- PyPI, accessed March 4, 2026, [https://pypi.org/project/discord-ext-voice-recv/](https://pypi.org/project/discord-ext-voice-recv/)  
55. Voice Related \- Pycord v2.7 Documentation, accessed March 4, 2026, [https://docs.pycord.dev/en/v2.7.0rc2/api/voice.html](https://docs.pycord.dev/en/v2.7.0rc2/api/voice.html)  
56. Voice Related \- Pycord v2.7 Documentation, accessed March 4, 2026, [https://docs.pycord.dev/en/v2.7.1/api/voice.html](https://docs.pycord.dev/en/v2.7.1/api/voice.html)  
57. Merge two wave files as bytes, so they play at the same time in Python? \- Stack Overflow, accessed March 4, 2026, [https://stackoverflow.com/questions/75640096/merge-two-wave-files-as-bytes-so-they-play-at-the-same-time-in-python](https://stackoverflow.com/questions/75640096/merge-two-wave-files-as-bytes-so-they-play-at-the-same-time-in-python)  
58. discord.sinks.mp3 \- Pycord v2.7 Documentation, accessed March 4, 2026, [https://docs.pycord.dev/en/v2.7.0rc2/\_modules/discord/sinks/mp3.html](https://docs.pycord.dev/en/v2.7.0rc2/_modules/discord/sinks/mp3.html)  
59. Record silence at the beginning and end of a recording \- Stack Overflow, accessed March 4, 2026, [https://stackoverflow.com/questions/75526842/record-silence-at-the-beginning-and-end-of-a-recording](https://stackoverflow.com/questions/75526842/record-silence-at-the-beginning-and-end-of-a-recording)  
60. Voice Related \- Pycord v0.1 Documentation, accessed March 4, 2026, [https://docs.pycord.dev/de/master/api/voice.html](https://docs.pycord.dev/de/master/api/voice.html)  
61. Changelog \- Pycord v2.6 Documentation, accessed March 4, 2026, [https://docs.pycord.dev/en/v2.6.1/changelog.html](https://docs.pycord.dev/en/v2.6.1/changelog.html)  
62. 10 Best Open-Source LLMs 2026: Llama 3.1, Gemma 2 & Command R+ \- Vertu, accessed March 4, 2026, [https://vertu.com/lifestyle/top-10-open-source-llms-for-2025-a-deep-dive-into-the-future-of-ai/](https://vertu.com/lifestyle/top-10-open-source-llms-for-2025-a-deep-dive-into-the-future-of-ai/)  
63. Choosing the right LLM: Llama vs Mistral vs DeepSeek | by Murilo Gustineli \- AI Advances, accessed March 4, 2026, [https://ai.gopubby.com/choosing-the-right-llm-llama-vs-mistral-vs-deepseek-6577136a895b](https://ai.gopubby.com/choosing-the-right-llm-llama-vs-mistral-vs-deepseek-6577136a895b)  
64. Benchmarking Open-Source LLMs: LLaMA vs Mistral vs Gemma \- DZone, accessed March 4, 2026, [https://dzone.com/articles/benchmarking-open-source-llama-mistral-gemma](https://dzone.com/articles/benchmarking-open-source-llama-mistral-gemma)  
65. Mistral 7b vs llama3 8b : r/ollama \- Reddit, accessed March 4, 2026, [https://www.reddit.com/r/ollama/comments/1d7gikb/mistral\_7b\_vs\_llama3\_8b/](https://www.reddit.com/r/ollama/comments/1d7gikb/mistral_7b_vs_llama3_8b/)  
66. Text-to-SQL Performance: A Head-to-Head Comparison of Llama 3.1, Qwen 2.5, and GPT-4.5 Turbo \- Leading Torch, accessed March 4, 2026, [https://www.leadingtorch.com/2025/12/09/text-to-sql-performance-a-head-to-head-comparison-of-llama-3-1-qwen-2-5-and-gpt-4-5-turbo/](https://www.leadingtorch.com/2025/12/09/text-to-sql-performance-a-head-to-head-comparison-of-llama-3-1-qwen-2-5-and-gpt-4-5-turbo/)  
67. Context length \- Ollama's documentation, accessed March 4, 2026, [https://docs.ollama.com/context-length](https://docs.ollama.com/context-length)  
68. Ollama Token Context Limit: What Happens When You Exceed It? \- Arsturn, accessed March 4, 2026, [https://www.arsturn.com/blog/what-happens-when-you-exceed-the-token-context-limit-in-ollama](https://www.arsturn.com/blog/what-happens-when-you-exceed-the-token-context-limit-in-ollama)  
69. PSA for Ollama Users: Your Context Length Might Be Lower Than You Think \- Reddit, accessed March 4, 2026, [https://www.reddit.com/r/LocalLLaMA/comments/1nffm7r/psa\_for\_ollama\_users\_your\_context\_length\_might\_be/](https://www.reddit.com/r/LocalLLaMA/comments/1nffm7r/psa_for_ollama_users_your_context_length_might_be/)  
70. How to increase context length of local LLMs in Ollama | LocalLLM.in, accessed March 4, 2026, [https://localllm.in/blog/local-llm-increase-context-length-ollama](https://localllm.in/blog/local-llm-increase-context-length-ollama)  
71. Chat history and embedding truncation happens silently with no user-visible indication \#14259 \- GitHub, accessed March 4, 2026, [https://github.com/ollama/ollama/issues/14259](https://github.com/ollama/ollama/issues/14259)  
72. Fixing Context Limits in OpenCode \+ Ollama | by stouf | Jan, 2026 \- Medium, accessed March 4, 2026, [https://stouf.medium.com/fixing-context-limits-in-opencode-ollama-1d820b332b41](https://stouf.medium.com/fixing-context-limits-in-opencode-ollama-1d820b332b41)  
73. 2024 Open Source AI Models Analysis——Llama, Qwen, Mistral AI, DeepSeek \- 莫尔索随笔, accessed March 4, 2026, [https://liduos.com/en/open-source-ai-models-2025-llama-qwen-mistral-deepseek.html](https://liduos.com/en/open-source-ai-models-2025-llama-qwen-mistral-deepseek.html)  
74. Mistral 3.1 vs Gemma 3: Which is the Better Model? \- Analytics Vidhya, accessed March 4, 2026, [https://www.analyticsvidhya.com/blog/2025/03/mistral-3-1-vs-gemma-3/](https://www.analyticsvidhya.com/blog/2025/03/mistral-3-1-vs-gemma-3/)  
75. The Best Speech Recognition API in 2025: A Head-to-Head Comparison | Voice Writer Blog, accessed March 4, 2026, [https://voicewriter.io/blog/best-speech-recognition-api-2025](https://voicewriter.io/blog/best-speech-recognition-api-2025)  
76. Whisper AI \- Professional Voice to Text Transcription, accessed March 4, 2026, [https://whisperai.com/](https://whisperai.com/)  
77. Best open source speech-to-text (STT) model in 2026 (with benchmarks) | Blog \- Northflank, accessed March 4, 2026, [https://northflank.com/blog/best-open-source-speech-to-text-stt-model-in-2026-benchmarks](https://northflank.com/blog/best-open-source-speech-to-text-stt-model-in-2026-benchmarks)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADEAAAAXCAYAAACiaac3AAACUElEQVR4Xu2Wz4uOURTHj1BkQtkQmqb8SNmgKD+yUdI005SUhYVibyE/syArWyWyEf4BCzayUBYa2c5MzaxGYoVSLEh8P517573v6X0ez3ijKc+3PvXce8993nPOc869r1mrVq3+pZaJzWKnWBPWSg2I7WJ1XKjQBnE1TjbVUjEijsWFHjonPog34qP4KQ52WZitEDfFJ3M7bF6JLaVRED7cE1/iQhOdEe/MX0Am6rRIPBQr03ixOCV+iKPZSLojronlacwzgRDU7mwUdMLcplEQW8UDc8dxYD46Yv5DF8I8c9/F/mIMfN2sy2nufTGX9dg8mbP2myDI2l4xIcbMP998tc0866NhPjtNkOibedZ3zFl44Nh8LuYQX/eW2Gg1QeDscTEtnppv6kc0axTO0ScEibCh+UvRI9iRxFKUF2W8ziqCIADKhvKhjP6GcBjnboslYS2LLM+Y250t5leJJ+m5Mgga6624YfVHYT+iIZ+ZO1Sl6+YB3LVOGVMRl9IaqgyiFJvphZdij/VfVpvElPlJVCf68Lx5T2aRUEobP7IaBZHFRl6QG/xPNCgmrds53rt+zsJFvVMJOWGU2z7zU4sDgjXuEaDs8wHB+FDaU6sh87uBY5bLqanWmifhpHWcoy8eiV1pjGjycet2hmw/N296nksOi68JxvFgqBX9QkauWOcSqxONeNq6HTggXqdnxJd6IYaDHf8ISEAvkQBKqVE59SPKIH/yyP3CLq6VxIsSRRsoL8pWC0I0XO7+Jlz0bQtLnB7xFKij11+KVv+9fgF00o3ArD7DhQAAAABJRU5ErkJggg==>