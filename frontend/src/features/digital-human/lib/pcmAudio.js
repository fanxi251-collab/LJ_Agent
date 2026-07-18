export function float32ToInt16(samples) {
  const result = new Int16Array(samples.length);
  for (let index = 0; index < samples.length; index += 1) {
    const sample = Math.max(-1, Math.min(1, samples[index]));
    result[index] = sample < 0 ? sample * 32768 : sample * 32767;
  }
  return result;
}

export function pcmRms(samples) {
  if (!samples.length) return 0;
  let sum = 0;
  for (const sample of samples) {
    const normalized = sample / 32768;
    sum += normalized * normalized;
  }
  return Math.sqrt(sum / samples.length);
}

export function float32Metrics(samples) {
  if (!samples.length) return { rms: 0, peak: 0, clippedRatio: 0 };
  let squareSum = 0;
  let peak = 0;
  let clipped = 0;
  for (const rawSample of samples) {
    const sample = Math.max(-1, Math.min(1, rawSample));
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
