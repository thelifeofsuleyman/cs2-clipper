"use strict";

const baseline = document.querySelector("#baseline-fps");
const target = document.querySelector("#target-fps");
const extraTime = document.querySelector("#added-time");
const extraTimeLabel = document.querySelector("#added-time-label");
const estimate = document.querySelector("#estimated-fps");
const headroom = document.querySelector("#headroom");
const note = document.querySelector("#fps-note");

function showScenario() {
  const before = baseline.valueAsNumber;
  const goal = target.valueAsNumber;
  const added = extraTime.valueAsNumber;
  extraTimeLabel.textContent = `${added.toFixed(1)} ms`;
  extraTime.setAttribute("aria-valuetext", `${added.toFixed(1)} milliseconds`);

  if (!baseline.validity.valid || !target.validity.valid || !Number.isFinite(before) || !Number.isFinite(goal)) {
    estimate.textContent = "—";
    headroom.textContent = "—";
    note.textContent = "Enter whole FPS values from 1 to 1,000.";
    return;
  }

  const frameTime = 1000 / before;
  const modeledFrameTime = frameTime + added;
  const fps = 1000 / modeledFrameTime;
  const targetFrameTime = 1000 / goal;
  const budget = Math.max(0, targetFrameTime - frameTime);

  estimate.textContent = `${Number(fps.toFixed(1))} FPS`;
  headroom.textContent = `${budget.toFixed(2)} ms`;

  if (goal > before) {
    note.textContent = `Your ${goal} FPS target is higher than your capture-off baseline.`;
  } else if (modeledFrameTime - targetFrameTime > 1e-9) {
    note.textContent = `This scenario puts you below your ${goal} FPS target.`;
  } else {
    note.textContent = `This scenario meets your ${goal} FPS target.`;
  }
}

for (const input of [baseline, target, extraTime]) {
  input.addEventListener("input", showScenario);
}
showScenario();
