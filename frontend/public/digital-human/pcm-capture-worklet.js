class PcmCaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = [];
    this.targetRate = 16000;
    this.samplesPerChunk = 1600;
  }

  process(inputs) {
    const input = inputs[0]?.[0];
    if (!input?.length) return true;
    const ratio = sampleRate / this.targetRate;
    for (let offset = 0; offset < input.length; offset += ratio) {
      const index = Math.min(input.length - 1, Math.floor(offset));
      const sample = Math.max(-1, Math.min(1, input[index]));
      this.buffer.push(sample);
      if (this.buffer.length >= this.samplesPerChunk) {
        const samples = this.buffer.splice(0, this.samplesPerChunk);
        const metrics = calculateMetrics(samples);
        const pcm = Int16Array.from(samples, (value) =>
          value < 0 ? value * 32768 : value * 32767,
        );
        // Metrics travel beside each transferable PCM block so quality checks never duplicate audio storage.
        this.port.postMessage({ type: "pcm", buffer: pcm.buffer, metrics }, [pcm.buffer]);
      }
    }
    return true;
  }
}

function calculateMetrics(samples) {
  let squareSum = 0;
  let peak = 0;
  let clipped = 0;
  for (const sample of samples) {
    const absolute = Math.abs(sample);
    squareSum += sample * sample;
    peak = Math.max(peak, absolute);
    if (absolute >= 0.98) clipped += 1;
  }
  return {
    rms: Math.sqrt(squareSum / samples.length),
    peak,
    clippedRatio: clipped / samples.length,
  };
}

registerProcessor("pcm-capture-processor", PcmCaptureProcessor);
