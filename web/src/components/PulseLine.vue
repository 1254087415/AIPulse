<script setup lang="ts">
const props = withDefaults(defineProps<{ alive?: boolean }>(), { alive: true })
</script>

<template>
  <div class="pulse-line" :class="{ flatline: !props.alive }" aria-hidden="true">
    <svg viewBox="0 0 120 28" preserveAspectRatio="none" class="trace">
      <path
        d="M0 14 H22 L26 14 L30 6 L34 22 L38 14 L42 14 H58 L62 14 L66 8 L70 20 L74 14 L78 14 H120"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        pathLength="200"
      />
    </svg>
    <span class="dot"></span>
  </div>
</template>

<style scoped>
.pulse-line {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--signal);
  width: 140px;
}

.trace {
  flex: 1;
  height: 22px;
  overflow: visible;
}

.trace path {
  stroke-dasharray: 200;
  stroke-dashoffset: 200;
  animation: draw 1.6s ease-in-out infinite;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
  box-shadow: 0 0 0 0 currentColor;
  animation: throb 1.6s ease-in-out infinite;
}

.flatline .trace path {
  animation: none;
  stroke-dashoffset: 0;
  opacity: 0.35;
}

.flatline .dot {
  animation: none;
  opacity: 0.35;
}

@keyframes draw {
  0% {
    stroke-dashoffset: 200;
  }
  45% {
    stroke-dashoffset: 0;
  }
  60% {
    stroke-dashoffset: 0;
  }
  100% {
    stroke-dashoffset: -200;
  }
}

@keyframes throb {
  0%,
  60% {
    transform: scale(1);
    opacity: 1;
  }
  30% {
    transform: scale(1.35);
    opacity: 0.85;
  }
  100% {
    transform: scale(1);
    opacity: 0.4;
  }
}

@media (prefers-reduced-motion: reduce) {
  .trace path {
    animation: none;
    stroke-dashoffset: 0;
  }
  .dot {
    animation: none;
  }
}
</style>
