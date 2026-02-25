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
    
    def __init__(self, shapenet_root='/media/tianyi/Tiantian/tianyiStudy/DataSets/ShapeNetCore.v2'):
        self.shapenet_root = shapenet_root
        self.categories = self._load_categories()
        self.object_cache = {}
        print(f"ShapeNet Loader initialized with {len(self.categories)} categories")
        
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
    
    def get_random_objects(self, n=2, same_category=False):
        """
        Sample random objects from ShapeNet.
        
        Args:
            n: Number of objects to sample
            same_category: If True, sample from the same category
            
        Returns:
            List of trimesh objects
        """
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
                
                objects.append(mesh)
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
