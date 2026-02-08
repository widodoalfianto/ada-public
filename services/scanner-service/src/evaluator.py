class ConditionEvaluator:
    @staticmethod
    def evaluate(history: list) -> list:
        """
        Evaluate technical conditions and return a list of raw signals.
        Returns list of dict: {'signal_code': str, 'timestamp': int, 'data': dict}
        """
        signals = []
        if not history:
            return []
            
        current = history[0]
        indicators = current.get('indicators', {})
        
        # Use current time for the alert timestamp (notification time)
        from datetime import datetime, timezone
        timestamp = int(datetime.now(timezone.utc).timestamp())
        
        # Previous day for Crossover checks
        previous = history[1] if len(history) > 1 else None
        prev_ind = previous.get('indicators', {}) if previous else {}

        # Helpers
        def get(d, k): return d.get(k)
        
        # --- 1. Moving Average Crossovers (EMA 9 vs SMA 20) ---
        c_fast = get(indicators, 'ema_9')
        c_slow = get(indicators, 'sma_20')
        p_fast = get(prev_ind, 'ema_9')
        p_slow = get(prev_ind, 'sma_20')
        
        if all(v is not None for v in [c_fast, c_slow, p_fast, p_slow]):
            # Bullish (Golden Cross)
            if p_fast <= p_slow and c_fast > c_slow:
                signals.append({
                    "signal_code": "GOLDEN_CROSS",
                    "timestamp": timestamp,
                    "data": {
                        "ema_9": round(c_fast, 2),
                        "sma_20": round(c_slow, 2)
                    }
                })
            # Bearish (Death Cross)
            elif p_fast >= p_slow and c_fast < c_slow:
                signals.append({
                    "signal_code": "DEATH_CROSS",
                    "timestamp": timestamp,
                    "data": {
                        "ema_9": round(c_fast, 2),
                        "sma_20": round(c_slow, 2)
                    }
                })

        return signals
