"""
ShapeNet Data Loader for Pseudo-Demonstration Generation
Based on Instant Policy paper (Appendix D)
"""
import os
import glob
import random
import trimesh
import numpy as np
from pathlib import Path


class ShapeNetLoader:
    """Load and manage ShapeNet objects for pseudo-demonstration generation."""
    
    def __init__(self, shapenet_root='/media/tianyi/Tiantian/tianyiStudy/DataSets/ShapeNetCore.v2', preload_size=0, aggressive_preload=False):
        self.shapenet_root = shapenet_root
        self.categories = self._load_categories()
        self.object_cache = {}
        self._cache_lock = __import__('threading').Lock()
        print(f"ShapeNet Loader initialized with {len(self.categories)} categories")
        # Pre-load a pool of meshes into memory for fast sampling
        self._preloaded_meshes = []
        if aggressive_preload:
            # Aggressive mode: preload many meshes (10-30 min startup, but much faster generation)
            print(f"Aggressive preload mode: loading {preload_size} meshes (this will take 10-30 minutes)...")
            self._preload_mesh_pool(pool_size=preload_size)
        elif preload_size > 0:
            self._preload_mesh_pool(pool_size=preload_size)
        else:
            print("✓ 快速启动模式：按需加载 mesh（preload_size=0）")
        
    def _load_categories(self):
        """Load all available ShapeNet categories."""
        categories = {}
        category_dirs = [d for d in os.listdir(self.shapenet_root) 
                        if os.path.isdir(os.path.join(self.shapenet_root, d))]
        
        for cat_id in category_dirs:
            cat_path = os.path.join(self.shapenet_root, cat_id)
            # Find all model files in this category
            models = []
            for model_dir in os.listdir(cat_path):
                model_path = os.path.join(cat_path, model_dir, 'models', 'model_normalized.obj')
                if os.path.exists(model_path):
                    models.append(model_path)
            
            if models:
                categories[cat_id] = models
                
        return categories
    
    def _preload_mesh_pool(self, pool_size=500):
        """Pre-load a pool of meshes into memory to avoid repeated network I/O."""
        import random as _random
        print(f"Pre-loading {pool_size} meshes into memory...")
        all_paths = [p for paths in self.categories.values() for p in paths]
        sampled_paths = _random.sample(all_paths, min(pool_size, len(all_paths)))
        loaded = 0
        for model_path in sampled_paths:
            try:
                mesh = trimesh.load(model_path, force='mesh', skip_materials=True)
                bounds = mesh.bounds
                size = bounds[1] - bounds[0]
                max_dim = np.max(size)
                if max_dim > 0:
                    mesh.apply_scale(0.15 / max_dim)
                mesh.vertices -= mesh.centroid
                if len(mesh.faces) > 0:
                    self._preloaded_meshes.append(mesh)
                    loaded += 1
            except Exception:
                continue
        print(f"Pre-loaded {loaded} meshes into memory")

    def get_random_objects(self, n=2, same_category=False):
        """
        Sample random objects from the preloaded mesh pool.
        """
        if self._preloaded_meshes:
            return [m.copy() for m in random.sample(self._preloaded_meshes, min(n, len(self._preloaded_meshes)))]

        # Fallback: load from disk
        objects = []
        
        if same_category:
            # Sample from the same category
            cat_id = random.choice(list(self.categories.keys()))
            model_paths = random.sample(self.categories[cat_id], min(n, len(self.categories[cat_id])))
        else:
            # Sample from different categories
            model_paths = []
            for _ in range(n):
                cat_id = random.choice(list(self.categories.keys()))
                model_path = random.choice(self.categories[cat_id])
                model_paths.append(model_path)
        
        # Load meshes
        for model_path in model_paths:
            try:
                # Check cache first
                with self._cache_lock:
                    if model_path in self.object_cache:
                        objects.append(self.object_cache[model_path].copy())
                        continue

                # Load with trimesh, skip textures (only need geometry for depth rendering)
                mesh = trimesh.load(model_path, force='mesh', skip_materials=True)

                # Normalize scale (paper uses objects of similar size)
                bounds = mesh.bounds
                size = bounds[1] - bounds[0]
                max_dim = np.max(size)
                if max_dim > 0:
                    mesh.apply_scale(0.15 / max_dim)  # Scale to ~15cm max dimension

                # Center the mesh
                mesh.vertices -= mesh.centroid

                # Cache the processed mesh
                with self._cache_lock:
                    self.object_cache[model_path] = mesh

                objects.append(mesh.copy())
            except Exception as e:
                print(f"Failed to load {model_path}: {e}")
                # Retry with another object
                return self.get_random_objects(n, same_category)
        
        return objects
    
    def get_num_categories(self):
        """Get number of available categories."""
        return len(self.categories)
    
    def get_num_models(self):
        """Get total number of available models."""
        return sum(len(models) for models in self.categories.values())


if __name__ == '__main__':
    # Test the loader
    loader = ShapeNetLoader()
    print(f"Total categories: {loader.get_num_categories()}")
    print(f"Total models: {loader.get_num_models()}")
    
    # Sample some objects
    objects = loader.get_random_objects(n=2)
    print(f"Sampled {len(objects)} objects")
    for i, obj in enumerate(objects):
        print(f"  Object {i}: {len(obj.vertices)} vertices, {len(obj.faces)} faces")
