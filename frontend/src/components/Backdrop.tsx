import { useEffect, useRef } from "react";

import { startLiquid, trackSheen } from "../lib/liquid";

/**
 * What is behind the page: three soft shapes that are always there, a canvas
 * of flowing light where WebGL is available, and a layer of fine grain.
 * All of it is decoration and is hidden from assistive technology.
 */
export function Backdrop() {
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const stopLiquid = canvas.current ? startLiquid(canvas.current) : () => undefined;
    const stopSheen = trackSheen();
    return () => {
      stopLiquid();
      stopSheen();
    };
  }, []);

  return (
    <div className="backdrop" aria-hidden="true">
      <div className="backdrop-blobs">
        <span />
        <span />
        <span />
      </div>
      <canvas ref={canvas} className="backdrop-canvas" />
      <div className="backdrop-grain" />
    </div>
  );
}
