"use client";

import { useEffect, useRef } from "react";
import { createChart, ColorType } from "lightweight-charts";

export function TradingChart({ data, markers = [] }: { data: any[], markers?: any[] }) {
  const chartContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartContainerRef.current || data.length === 0) return;

    const handleResize = () => {
      chart.applyOptions({ width: chartContainerRef.current?.clientWidth });
    };

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#71716f",
        fontFamily: "var(--font-mono), monospace",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "rgba(255,176,0,0.04)" },
        horzLines: { color: "#1c1c1f" },
      },
      crosshair: {
        vertLine: { color: "#ffb000", width: 1, style: 2, labelBackgroundColor: "#ffb000" },
        horzLine: { color: "#ffb000", width: 1, style: 2, labelBackgroundColor: "#ffb000" },
      },
      rightPriceScale: { borderColor: "#1c1c1f" },
      timeScale: { borderColor: "#1c1c1f" },
      width: chartContainerRef.current.clientWidth,
      height: 400,
    });

    const candlestickSeries = chart.addCandlestickSeries({
      upColor: "#3ad07a",
      downColor: "#ff4d4d",
      borderVisible: false,
      wickUpColor: "#3ad07a",
      wickDownColor: "#ff4d4d",
    });

    const clean = data.filter(
      (d) =>
        d &&
        typeof d.open === "number" &&
        typeof d.high === "number" &&
        typeof d.low === "number" &&
        typeof d.close === "number" &&
        !isNaN(d.open) && !isNaN(d.high) && !isNaN(d.low) && !isNaN(d.close)
    );
    candlestickSeries.setData(clean);
    if (markers.length > 0) {
      candlestickSeries.setMarkers(markers);
    }

    chart.timeScale().fitContent();

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [data, markers]);

  return <div ref={chartContainerRef} className="w-full h-[400px]" />;
}
