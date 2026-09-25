/**
 * Floating Triangle Particles - Canvas Background
 * Creates an organic, living background of drifting triangles
 * with subtle connections and glow effects.
 */
(function () {
  'use strict';

  const canvas = document.getElementById('triangle-particles-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  // ── Configuration ──────────────────────────────────────────
  const CONFIG = {
    particleCount: 60,          // number of triangles
    minSize: 6,
    maxSize: 22,
    minSpeed: 0.15,
    maxSpeed: 0.55,
    connectionDistance: 160,     // px – draw line between nearby triangles
    connectionOpacity: 0.08,
    colors: [
      'rgba(34,197,94,',    // green-500
      'rgba(16,185,129,',   // emerald-500
      'rgba(52,211,153,',   // emerald-400
      'rgba(74,222,128,',   // green-400
      'rgba(132,204,22,',   // lime-500
      'rgba(163,230,53,',   // lime-400
      'rgba(20,184,166,',   // teal-500
      'rgba(45,212,191,',   // teal-400
    ],
    mouseRadius: 120,           // repel radius around cursor
    mouseForce: 0.6,
  };

  let particles = [];
  let w, h;
  let mouse = { x: -9999, y: -9999 };
  let animId;

  // ── Resize ─────────────────────────────────────────────────
  function resize() {
    w = canvas.width = window.innerWidth;
    h = canvas.height = window.innerHeight;
  }
  window.addEventListener('resize', resize);
  resize();

  // ── Mouse tracking ─────────────────────────────────────────
  window.addEventListener('mousemove', (e) => {
    mouse.x = e.clientX;
    mouse.y = e.clientY;
  });
  window.addEventListener('mouseleave', () => {
    mouse.x = -9999;
    mouse.y = -9999;
  });

  // ── Particle class ─────────────────────────────────────────
  class Triangle {
    constructor() {
      this.reset(true);
    }

    reset(initial) {
      this.size = CONFIG.minSize + Math.random() * (CONFIG.maxSize - CONFIG.minSize);
      this.halfSize = this.size / 2;

      // position
      this.x = Math.random() * w;
      this.y = initial ? Math.random() * h : h + this.size + Math.random() * 60;

      // velocity – mostly upward drift
      this.vx = (Math.random() - 0.5) * CONFIG.maxSpeed;
      this.vy = -(CONFIG.minSpeed + Math.random() * (CONFIG.maxSpeed - CONFIG.minSpeed));

      // rotation
      this.angle = Math.random() * Math.PI * 2;
      this.rotSpeed = (Math.random() - 0.5) * 0.012;

      // style
      this.colorBase = CONFIG.colors[Math.floor(Math.random() * CONFIG.colors.length)];
      this.baseOpacity = 0.12 + Math.random() * 0.28;
      this.opacity = this.baseOpacity;

      // pulsing
      this.pulseSpeed = 0.005 + Math.random() * 0.015;
      this.pulseOffset = Math.random() * Math.PI * 2;

      // outline vs filled
      this.filled = Math.random() > 0.4;
      this.lineWidth = 0.8 + Math.random() * 1.2;
    }

    update(time) {
      // drift
      this.x += this.vx;
      this.y += this.vy;

      // gentle sine sway
      this.x += Math.sin(time * 0.0005 + this.pulseOffset) * 0.15;

      // rotation
      this.angle += this.rotSpeed;

      // pulse opacity
      this.opacity = this.baseOpacity + Math.sin(time * this.pulseSpeed + this.pulseOffset) * 0.08;
      this.opacity = Math.max(0.04, Math.min(this.opacity, 0.5));

      // mouse repulsion
      const dx = this.x - mouse.x;
      const dy = this.y - mouse.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist < CONFIG.mouseRadius && dist > 0) {
        const force = (1 - dist / CONFIG.mouseRadius) * CONFIG.mouseForce;
        this.x += (dx / dist) * force;
        this.y += (dy / dist) * force;
      }

      // wrap / recycle
      if (this.y < -this.size * 2) this.reset(false);
      if (this.x < -this.size * 2) this.x = w + this.size;
      if (this.x > w + this.size * 2) this.x = -this.size;
    }

    draw() {
      ctx.save();
      ctx.translate(this.x, this.y);
      ctx.rotate(this.angle);

      ctx.beginPath();
      // equilateral triangle centred on origin
      const r = this.size;
      ctx.moveTo(0, -r);
      ctx.lineTo(r * 0.866, r * 0.5);
      ctx.lineTo(-r * 0.866, r * 0.5);
      ctx.closePath();

      const color = this.colorBase + this.opacity + ')';

      if (this.filled) {
        ctx.fillStyle = color;
        ctx.fill();
      } else {
        ctx.strokeStyle = color;
        ctx.lineWidth = this.lineWidth;
        ctx.stroke();
      }

      ctx.restore();
    }
  }

  // ── Initialise particles ───────────────────────────────────
  function init() {
    particles = [];
    for (let i = 0; i < CONFIG.particleCount; i++) {
      particles.push(new Triangle());
    }
  }
  init();

  // Re-init on large resize so density stays consistent
  let resizeTimer;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(init, 300);
  });

  // ── Draw connections ───────────────────────────────────────
  function drawConnections() {
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < CONFIG.connectionDistance) {
          const opacity = CONFIG.connectionOpacity * (1 - dist / CONFIG.connectionDistance);
          ctx.strokeStyle = `rgba(34,197,94,${opacity})`;
          ctx.lineWidth = 0.5;
          ctx.beginPath();
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.stroke();
        }
      }
    }
  }

  // ── Animation loop ─────────────────────────────────────────
  function animate(time) {
    ctx.clearRect(0, 0, w, h);

    // subtle radial glow in the centre
    const gradient = ctx.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, w * 0.7);
    gradient.addColorStop(0, 'rgba(16,185,129,0.03)');
    gradient.addColorStop(1, 'rgba(10,15,10,0)');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, w, h);

    drawConnections();

    for (const p of particles) {
      p.update(time);
      p.draw();
    }

    animId = requestAnimationFrame(animate);
  }

  animId = requestAnimationFrame(animate);

  // ── Cleanup (if ever needed) ───────────────────────────────
  window._stopTriangleParticles = function () {
    cancelAnimationFrame(animId);
  };
})();
