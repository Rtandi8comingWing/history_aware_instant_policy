"""
Continuous Pseudo-Demonstration Dataset using PyRender for depth rendering.
Strictly follows paper Appendix D rendering pipeline.
"""
from ip.utils.continuous_dataset import ContinuousPseudoDataset
from ip.utils.pseudo_demo_generator_pyrender import PseudoDemoGeneratorPyrender


class ContinuousPseudoDatasetPyrender(ContinuousPseudoDataset):
    """
    Identical to ContinuousPseudoDataset but uses PyRender depth cameras
    instead of trimesh surface sampling.
    """

    def _generation_worker(self, worker_id):
        """Background thread using PyRender generator."""
        import queue
        import time
        import gc
        import os

        # CRITICAL: Force EGL platform in each worker thread
        os.environ['PYOPENGL_PLATFORM'] = 'egl'
        os.environ['DISPLAY'] = ''  # Clear DISPLAY to avoid X11 interference

        # Import PyRender (will automatically use EGL platform from environment)
        import pyrender
        print(f"✓ Worker {worker_id}: PyRender using EGL platform")

        generator = PseudoDemoGeneratorPyrender()

        while not self.stop_generation.is_set():
            try:
                sample = self._generate_one_sample(generator)
                self.buffer.put(sample, timeout=1.0)
                self.samples_generated += 1

                if self.samples_generated % 50 == 0:
                    gc.collect()

            except queue.Full:
                time.sleep(0.1)
            except Exception as e:
                import traceback
                self.generation_errors += 1
                err_msg = str(e)
                with self._error_print_lock:
                    if self._last_error_msg != err_msg or self.generation_errors <= 3:
                        print(f"\n[Worker {worker_id}] Generation error #{self.generation_errors}: {err_msg}")
                        if self.generation_errors <= 2:
                            traceback.print_exc()
                        self._last_error_msg = err_msg
                    elif self.generation_errors % 100 == 0:
                        print(f"Worker {worker_id} error count: {self.generation_errors} (last: {err_msg[:80]})")
                time.sleep(0.1)
