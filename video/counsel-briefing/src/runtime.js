/* In-page motion runtime. Builds Web Animations from data-a attributes, which
 * HyperFrames' waapi adapter seeks frame by frame. Nothing here reads a clock,
 * generates a random number or touches the network: every frame is a pure
 * function of the requested time.
 *
 * Each scene is a HyperFrames sub-composition. Its template ends with
 *
 *     window.__serenataMotion(document.getElementById("<scene-id>"))
 *
 * and everything inside is timed relative to the scene, so a scene file does
 * not know where it sits in the video. The host's data-start is added here.
 *
 *   data-a        preset name
 *   data-at       seconds from the start of the enclosing [data-t0] element
 *   data-dur      seconds; overrides the preset's own
 *   data-stagger  on a parent: its direct [data-a] children start i * stagger apart
 */
window.__serenataMotion = (scope) => {
  const D = JSON.parse(document.getElementById('direction').textContent);
  const feel = D.motion.feel;
  const speed = D.motion.speed;

  const num = (el, key, fallback) => {
    const v = el.dataset[key];
    return v === undefined || v === '' ? fallback : parseFloat(v);
  };
  const snap = (dur) => `steps(${Math.max(1, Math.round(dur * feel))}, end)`;

  // The scene's root is mounted inside a host that carries the real data-start.
  const host = scope.parentElement ? scope.parentElement.closest('[data-start]') : null;
  const hostStart = host ? parseFloat(host.getAttribute('data-start')) : 0;
  const t0Of = (el) => {
    const owner = el.closest('[data-t0]');
    return owner && scope.contains(owner) ? parseFloat(owner.dataset.t0) : 0;
  };

  // Each preset returns { kf, dur, ease } and may set iterations.
  const P = {
    cut: () => ({ kf: [{ opacity: 0 }, { opacity: 1 }], dur: 0.001, ease: 'steps(1, end)' }),
    fade: () => ({ kf: [{ opacity: 0 }, { opacity: 1 }], dur: 0.4, ease: 'snap' }),
    pop: () => ({
      kf: [
        { opacity: 0, transform: 'scale(.9)' },
        { opacity: 1, transform: 'scale(1)' },
      ],
      dur: 0.35,
      ease: 'snap',
    }),
    up: () => ({
      kf: [
        { opacity: 0, transform: 'translateY(44px)' },
        { opacity: 1, transform: 'translateY(0)' },
      ],
      dur: 0.5,
      ease: 'snap',
    }),
    left: () => ({
      kf: [
        { opacity: 0, transform: 'translateX(-72px)' },
        { opacity: 1, transform: 'translateX(0)' },
      ],
      dur: 0.5,
      ease: 'snap',
    }),
    right: () => ({
      kf: [
        { opacity: 0, transform: 'translateX(72px)' },
        { opacity: 1, transform: 'translateX(0)' },
      ],
      dur: 0.5,
      ease: 'snap',
    }),
    wipeX: () => ({
      kf: [{ clipPath: 'inset(0 100% 0 0)' }, { clipPath: 'inset(0 0% 0 0)' }],
      dur: 0.55,
      ease: 'snap',
    }),
    wipeY: () => ({
      kf: [{ clipPath: 'inset(100% 0 0 0)' }, { clipPath: 'inset(0% 0 0 0)' }],
      dur: 0.55,
      ease: 'snap',
    }),
    bar: () => ({
      kf: [{ transform: 'scaleX(0)' }, { transform: 'scaleX(1)' }],
      dur: 0.7,
      ease: 'snap',
    }),
    barY: () => ({
      kf: [{ transform: 'scaleY(0)' }, { transform: 'scaleY(1)' }],
      dur: 0.5,
      ease: 'snap',
    }),
    grow: () => ({
      kf: [{ transform: 'scaleX(0)' }, { transform: 'scaleX(1)' }],
      dur: 10,
      ease: 'linear',
      fixed: true,
    }),
    draw: () => ({
      kf: [{ strokeDashoffset: 1 }, { strokeDashoffset: 0 }],
      dur: 1.6,
      ease: 'snap',
    }),
    type: (el) => {
      const chars = num(el, 'n', 10);
      return {
        kf: [{ width: '0ch' }, { width: `${chars}ch` }],
        dur: chars / 24,
        ease: `steps(${Math.max(1, Math.round(chars))}, end)`,
      };
    },
    roll: (el) => {
      const d = num(el, 'digit', 0);
      const stops = 10 + d;
      return {
        kf: [{ transform: 'translateY(0%)' }, { transform: `translateY(-${stops * 5}%)` }],
        dur: 0.9,
        ease: `steps(${Math.max(1, stops)}, end)`,
      };
    },
    cursor: (el) => {
      const cycle = 0.8;
      const total = num(el, 'dur', 10);
      return {
        kf: [
          { opacity: 1, offset: 0 },
          { opacity: 1, offset: 0.5 },
          { opacity: 0, offset: 0.5 },
          { opacity: 0, offset: 1 },
        ],
        dur: cycle,
        ease: 'linear',
        fixed: true,
        iterations: Math.max(1, Math.floor(total / cycle)),
      };
    },
    push: (el) => ({
      kf: [{ transform: 'scale(1)' }, { transform: `scale(${1 + D.camera.push * D.camera.speed})` }],
      dur: num(el, 'dur', 10),
      ease: 'linear',
      fixed: true,
    }),
    // Anything else: data-from / data-to hold CSS declarations as JSON.
    tween: (el) => ({
      kf: [JSON.parse(el.dataset.from || '{}'), JSON.parse(el.dataset.to || '{}')],
      dur: 0.5,
      ease: 'snap',
    }),
  };

  // Stagger: children of [data-stagger] start i * step after the parent's own data-at.
  scope.querySelectorAll('[data-stagger]').forEach((parent) => {
    const step = num(parent, 'stagger', 0.1);
    const start = num(parent, 'at', 0);
    [...parent.children]
      .filter((c) => c.hasAttribute('data-a'))
      .forEach((c, i) => {
        c.dataset.at = (start + num(c, 'at', 0) + i * step).toFixed(3);
      });
  });

  scope.querySelectorAll('[data-a]').forEach((el) => {
    const make = P[el.dataset.a];
    if (!make) throw new Error(`unknown motion preset: ${el.dataset.a}`);
    const p = make(el);
    // A cursor's data-dur is how long it stays on screen, not one blink.
    const requested = el.dataset.a === 'cursor' ? p.dur : num(el, 'dur', p.dur);
    const dur = p.fixed ? requested : requested / speed;
    const ease = p.ease === 'snap' ? snap(dur) : p.ease;
    const delay = hostStart + t0Of(el) + num(el, 'at', 0);
    el.animate(p.kf, {
      duration: dur * 1000,
      delay: delay * 1000,
      easing: ease,
      fill: 'both',
      iterations: p.iterations || 1,
    }).pause();
  });
};
