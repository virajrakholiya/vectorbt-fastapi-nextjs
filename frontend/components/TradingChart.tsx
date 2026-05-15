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
        textColor: "#cbd5e1",
      },
      grid: {
        vertLines: { color: "#1e293b" },
        horzLines: { color: "#1e293b" },
      },
      width: chartContainerRef.current.clientWidth,
      height: 400,
    });

    const candlestickSeries = chart.addCandlestickSeries({
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
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
