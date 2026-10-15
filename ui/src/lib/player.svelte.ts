/** One shared audio element so only a single clip plays at a time. */
class Player {
  key = $state<string | null>(null);
  playing = $state(false);
  progress = $state(0);
  time = $state(0);
  private audio = new Audio();
  private onEnded: (() => void) | null = null;
  private range: [number, number] | null = null;

  constructor() {
    this.audio.preload = "auto";
    this.audio.addEventListener("ended", () => this.finish());
    this.audio.addEventListener("pause", () => (this.playing = false));
    this.audio.addEventListener("play", () => (this.playing = true));
    this.audio.addEventListener("timeupdate", () => {
      const { currentTime, duration } = this.audio;
      this.time = currentTime;
      if (this.range) {
        const [a, b] = this.range;
        this.progress = Math.min(1, (currentTime - a) / (b - a));
        if (currentTime >= b) this.finish();
      } else {
        this.progress = duration ? currentTime / duration : 0;
      }
    });
  }

  /** Play `url`; optionally only the [start, end] seconds range. */
  async play(key: string, url: string, opts: { onEnded?: () => void; range?: [number, number] } = {}) {
    this.onEnded = opts.onEnded ?? null;
    this.range = opts.range ?? null;
    this.key = key;
    this.progress = 0;
    const absolute = new URL(url, location.href).href;
    if (this.audio.src !== absolute) this.audio.src = absolute;
    this.audio.currentTime = this.range ? this.range[0] : 0;
    await this.audio.play().catch(() => {});
  }

  stop() {
    this.onEnded = null;
    this.audio.pause();
    this.playing = false;
  }

  private finish() {
    this.audio.pause();
    this.playing = false;
    this.progress = 1;
    const cb = this.onEnded;
    this.onEnded = null;
    cb?.();
  }
}

export const player = new Player();
