import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App";

// Polyfill لـ canvas.roundRect على المتصفحات القديمة
if (!CanvasRenderingContext2D.prototype.roundRect) {
  CanvasRenderingContext2D.prototype.roundRect = function(x, y, w, h, r) {
    r = Math.min(r, w / 2, h / 2);
    this.beginPath();
    this.moveTo(x + r, y);
    this.arcTo(x + w, y,     x + w, y + h, r);
    this.arcTo(x + w, y + h, x,     y + h, r);
    this.arcTo(x,     y + h, x,     y,     r);
    this.arcTo(x,     y,     x + w, y,     r);
    this.closePath();
    return this;
  };
}

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>
);
