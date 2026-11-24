function schedule(quality, repetitions, ease, interval) {
  if (quality < 0 || quality > 5) {
    throw new Error("quality must be between 0 and 5");
  }
  ease = ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02));
  if (ease < 1.3) ease = 1.3;
  ease = Math.round(ease * 10000) / 10000;
  if (quality < 3) return [0, ease, 1];
  let nextInterval = 1;
  if (repetitions === 1) nextInterval = 6;
  else if (repetitions > 1) nextInterval = Math.max(1, Math.round(interval * ease));
  return [repetitions + 1, ease, nextInterval];
}

module.exports = { schedule };
