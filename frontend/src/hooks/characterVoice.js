// Delivery styles use public character traits, never private story material.
const styles = {
  last_letter: {
    conductor: ["沉稳、从容", "male", 0.88, 0.92],
    secretary: ["谨慎、轻缓", "female", 0.96, 1.02],
    reporter: ["清晰、利落", "female", 1.04, 1.06],
    dealer: ["克制、讲究", "male", 0.96, 0.97],
  },
  rain_lock: {
    boss_wife: ["镇定、有分寸", "female", 0.94, 0.98],
    chef: ["急性子、直接", "male", 1.07, 0.98],
    guest: ["克制、疏离", "female", 0.91, 1.01],
    handyman: ["朴实、平稳", "male", 0.98, 0.94],
  },
  ravenel_manor: {
    irma: ["缓慢、神秘", "female", 0.87, 0.97],
    gaspard: ["紧绷、年轻", "male", 1.03, 1.04],
    eleonore: ["成熟、克制", "female", 0.91, 0.96],
    lestrade: ["年长、稳重", "male", 0.86, 0.9],
    basile: ["朴实、谨慎", "male", 0.94, 0.95],
    victoire: ["干练、讲究", "female", 1.02, 1.01],
    ophelie: ["轻缓、含蓄", "female", 0.92, 1.04],
    oscar: ["年轻、活跃", "male", 1.08, 1.08],
  },
};

const names = {
  male: /yunxi|yunjian|yunyang|yunfeng|yunhao|yunze|yunye|yunxia|yunlong|kangkang|li.?mu|grandpa|eddy|reed|rocko|康康|云希|云健|云扬/i,
  female: /xiaoxiao|xiaoyi|xiaohan|xiaomeng|xiaomo|xiaoxuan|xiaorui|xiaoshuang|huihui|yaoyao|ting.?ting|meijia|lili|grandma|flo|sandy|shelley|晓晓|晓伊|婷婷|慧慧|语舒/i,
};

const preferredNames = {
  conductor: /li.?mu|grandpa|yunjian/i, secretary: /语舒|xiaoyi/i,
  reporter: /婷婷|ting.?ting|xiaoxiao/i, dealer: /reed|yunye/i,
  boss_wife: /语舒|xiaorui/i, chef: /eddy|yunxi/i,
  guest: /shelley|xiaohan/i, handyman: /rocko|yunyang/i,
  irma: /语舒|xiaomo/i, gaspard: /eddy|yunxi/i,
  eleonore: /语舒|xiaorui/i, lestrade: /li.?mu|grandpa|yunjian/i,
  basile: /reed|yunyang/i, victoire: /婷婷|ting.?ting|xiaoxiao/i,
  ophelie: /shelley|xiaohan/i, oscar: /rocko|yunxia/i,
};

export function voiceKey(speaker) {
  return `${speaker.scriptId}:${speaker.id}`;
}

export function characterStyle(speaker = {}) {
  const [label, gender, rate, pitch] = styles[speaker.scriptId]?.[speaker.id] || ["自然、平稳", "", 0.98, 1];
  return { label, gender, rate, pitch, preferredNames: preferredNames[speaker.id] };
}

export function chineseVoices(voices) {
  return voices.filter((voice) => /^zh(?:[-_]|$)/i.test(voice.lang))
    .sort((a, b) => a.name.localeCompare(b.name));
}

export function chooseVoice(voices, style, preferredURI) {
  const preferred = voices.find((voice) => voice.voiceURI === preferredURI);
  if (preferred) return preferred;
  const score = (voice) =>
    (/^zh[-_]CN$/i.test(voice.lang) ? 5 : 0) +
    (/natural|premium|enhanced|neural|自然|增强/i.test(voice.name) ? 8 : 0) +
    (names[style.gender]?.test(voice.name) ? 12 : 0) +
    (style.preferredNames?.test(voice.name) ? 6 : 0);
  return [...voices].sort((a, b) => score(b) - score(a))[0] || null;
}

export function speechParts(text) {
  return (text.match(/[^。！？!?；;\n]+(?:[。！？!?；;\n]+[”’」』]?|$)/gu) || [])
    .map((part) => part.replace(/[*#`]/g, "").trim()).filter(Boolean);
}

export function delivery(style, emotion, rateOverride) {
  const rate = Number.isFinite(rateOverride) ? rateOverride : style.rate;
  const adjustment = { 烦躁: 0.04, 慌张: 0.04, 戒备: -0.03, 防守: -0.02, 松动: -0.02 }[emotion] || 0;
  return { rate: Math.max(0.75, Math.min(1.2, rate + adjustment)), pitch: style.pitch };
}

export class SpeechPlayer {
  constructor(synthesis, Utterance, schedule = setTimeout, unschedule = clearTimeout) {
    this.synthesis = synthesis;
    this.Utterance = Utterance;
    this.schedule = schedule;
    this.unschedule = unschedule;
    this.queue = [];
    this.active = null;
    this.timer = null;
    this.generation = 0;
  }

  enqueue(text, options) {
    this.queue.push(...speechParts(text).map((text) => ({ text, options })));
    this.next();
  }

  next() {
    if (this.active || this.timer !== null || !this.queue.length) return;
    const { text, options } = this.queue.shift();
    const utterance = new this.Utterance(text);
    utterance.lang = options.voice?.lang || "zh-CN";
    if (options.voice) utterance.voice = options.voice;
    utterance.rate = options.rate;
    utterance.pitch = options.pitch;
    this.active = utterance;
    const generation = this.generation;
    const finish = () => {
      if (generation !== this.generation || this.active !== utterance) return;
      this.active = null;
      const pause = /[？?][”’」』]?$/.test(text) ? 260 : /[；;]$/.test(text) ? 140 : 210;
      this.timer = this.schedule(() => {
        if (generation !== this.generation) return;
        this.timer = null;
        this.next();
      }, pause);
    };
    utterance.onend = finish;
    utterance.onerror = (event) => {
      if (generation !== this.generation || this.active !== utterance) return;
      // Browsers may block audio until a user gesture. Don't flood the queue.
      if (event.error === "not-allowed") this.stop();
      else finish();
    };
    this.synthesis.speak(utterance);
  }

  stop() {
    this.generation += 1;
    this.queue = [];
    this.active = null;
    if (this.timer !== null) this.unschedule(this.timer);
    this.timer = null;
    this.synthesis.cancel();
  }
}
