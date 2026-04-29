import time
import threading

total_signals_processed = 0
last_logged_count = 0
last_logged_time = time.time()


def increment_signal_count():
    global total_signals_processed
    total_signals_processed += 1


def get_total_signals():
    return total_signals_processed


def start_metrics_logger():
    def log_metrics():
        global last_logged_count, last_logged_time

        while True:
            time.sleep(5)

            current_time = time.time()
            elapsed = current_time - last_logged_time

            current_count = total_signals_processed
            delta = current_count - last_logged_count

            signals_per_sec = delta / elapsed if elapsed > 0 else 0

            print(
                f"[METRICS] Signals/sec: {signals_per_sec:.2f} | Total Signals: {current_count}"
            )

            last_logged_count = current_count
            last_logged_time = current_time

    thread = threading.Thread(target=log_metrics, daemon=True)
    thread.start()