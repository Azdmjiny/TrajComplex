"""Run from root: ATSCC/.venv/bin/python -m unittest discover -s ATSCC/tests -v."""

from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset

from ATSCC import (
    EncoderConfig, EmbeddingConfig, TrainingConfig, build_model, encode_scene,
    load_model, pool_hidden, save_model,
)
from ATSCC.train import fit_encoder, make_dataset, seed_everything
from complexity import estimate_complexity


ROOT = Path(__file__).resolve().parents[2]
SMALL = EncoderConfig(embed_dim=16, num_heads=4, num_layers=1, hidden_dim=32, dropout=0.0)


def temporary_directory():
    return tempfile.TemporaryDirectory(dir=os.environ.get("PI_SCRATCH_DIR"))


class ConfigTests(unittest.TestCase):
    def test_documented_defaults_and_json(self):
        encoder = EncoderConfig()
        self.assertEqual((encoder.input_dims, encoder.output_dims, encoder.embed_dim,
                          encoder.num_heads, encoder.num_layers, encoder.hidden_dim), (9, 8, 256, 4, 4, 512))
        self.assertEqual(EmbeddingConfig().pooling, "sum")
        self.assertEqual(TrainingConfig().epochs, 30)
        settings = json.loads((ROOT / "ATSCC/configs/encoder-default.json").read_text())
        self.assertEqual(settings["encoder"], encoder.to_dict())
        self.assertEqual(settings["training"], TrainingConfig().to_dict())
        self.assertEqual(settings["embedding"], EmbeddingConfig().to_dict())
        self.assertEqual(build_model().get_config(), encoder.to_dict())

    def test_invalid_configs(self):
        for values in ({"output_dims": 0}, {"embed_dim": 15}, {"dropout": float("nan")},
                       {"num_heads": True}, {"mask_probability": 1.0}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                EncoderConfig(**values)
        for values in ({"gem_p": 0}, {"batch_size": 0}, {"pooling": "typo"}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                EmbeddingConfig(**values)
        for values in ({"seed": -1}, {"epochs": 0}, {"temperature": 0}, {"weight_decay": -1}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                TrainingConfig(**values)


class PoolingTests(unittest.TestCase):
    def setUp(self):
        self.hidden = torch.tensor([[[-1., 2.], [3., -4.], [float("nan"), float("nan")]]])
        self.valid = torch.tensor([[True, True, False]])

    def test_all_pooling_rules(self):
        expected = {"sum": [2., -2.], "mean": [1., -1.], "gem": [2., -12**0.5 / 2**0.5],
                    "first": [-1., 2.], "last": [3., -4.], "max": [3., 2.]}
        before = self.hidden.clone()
        for mode, result in expected.items():
            with self.subTest(mode=mode):
                torch.testing.assert_close(pool_hidden(self.hidden, self.valid, pooling=mode), torch.tensor([result]))
        torch.testing.assert_close(self.hidden, before, equal_nan=True)
        torch.testing.assert_close(pool_hidden(self.hidden, pooling="gem", gem_p=1),
                                   pool_hidden(self.hidden, pooling="mean"))

    def test_mask_ignores_finite_padding_too(self):
        hidden = self.hidden.nan_to_num(1000)
        torch.testing.assert_close(pool_hidden(hidden, self.valid), torch.tensor([[2., -2.]]))

    def test_rejects_empty_nonfinite_and_bad_masks(self):
        for hidden, mask in ((self.hidden, torch.zeros_like(self.valid)),
                             (self.hidden, torch.ones_like(self.valid)),
                             (self.hidden, torch.ones(1, 3)),
                             (self.hidden, torch.ones(1, 2, dtype=torch.bool))):
            with self.subTest(mask=mask), self.assertRaises(ValueError):
                pool_hidden(hidden, mask)
        self.assertEqual(pool_hidden(torch.empty(0, 3, 8)).shape, (0, 8))


class EncoderTests(unittest.TestCase):
    def setUp(self):
        seed_everything(0)
        self.model = build_model(SMALL)
        self.features = np.random.default_rng(1).normal(size=(3, 7, 9)).astype(np.float32)
        self.features[1, 4:] = np.nan

    def test_inference_repeats_preserves_inputs_modes_and_order(self):
        before = self.features.copy()
        result = encode_scene(self.model, self.features, scene_id="hour_01")
        again = encode_scene(self.model, self.features)
        self.assertTrue(self.model.training)
        self.assertEqual(result.lengths, [7, 4, 7])
        self.assertEqual(result.embeddings.shape, (3, 8))
        np.testing.assert_array_equal(result.embeddings, again.embeddings)
        np.testing.assert_array_equal(before, self.features)
        self.assertTrue(np.isfinite(result.embeddings).all())
        json.dumps(result.to_dict(), allow_nan=False)
        single = encode_scene(self.model, [self.features[1]], config=EmbeddingConfig(batch_size=1))
        np.testing.assert_allclose(single.embeddings[0], result.embeddings[1], atol=1e-6)
        self.model.eval()
        encode_scene(self.model, self.features)
        self.assertFalse(self.model.training)

    def test_default_sum_and_mean_lengths(self):
        summed = encode_scene(self.model, self.features)
        mean = encode_scene(self.model, self.features, config=EmbeddingConfig(pooling="mean", batch_size=1))
        np.testing.assert_allclose(summed.embeddings, mean.embeddings * np.array(summed.lengths)[:, None], atol=1e-6)

    def test_empty_scene_and_invalid_data(self):
        result = encode_scene(self.model, np.empty((0, 5, 9)))
        self.assertEqual(result.embeddings.shape, (0, 8))
        self.assertEqual(estimate_complexity(result.embeddings).reason, "insufficient_samples")
        partial = self.features.copy()
        partial[0, 0, 0] = np.nan
        for values in (partial, np.ones((2, 4, 3)), np.ones((2, 9)),
                       [np.full((2, 9), np.nan)], [np.full((2, 9), np.inf)],
                       np.full((1, 2, 9), "bad")):
            with self.subTest(type=type(values)), self.assertRaises(ValueError):
                encode_scene(self.model, values)
        with self.assertRaises(ValueError):
            encode_scene(self.model, self.features, scene_id=42)

    def test_restores_mode_on_forward_failure(self):
        with patch.object(self.model, "forward", side_effect=RuntimeError("failure")):
            with self.assertRaises(RuntimeError):
                encode_scene(self.model, self.features)
        self.assertTrue(self.model.training)

    def test_masking_is_twenty_percent_not_eighty(self):
        mask = self.model.generate_random_mask(torch.empty(200, 500, 9), 0.2)
        self.assertTrue(0.19 < mask.float().mean().item() < 0.21)
        self.assertFalse(self.model.generate_random_mask(torch.empty(2, 5, 9), 0).any())

    def test_forward_padding_causality_no_mutation_and_backward(self):
        self.model.eval()
        x = torch.tensor(self.features)
        before = x.clone()
        out = self.model(x)
        torch.testing.assert_close(x, before, equal_nan=True)
        self.assertTrue(out[1, 4:].isnan().all())
        prefix = self.model(x[:, :3])
        torch.testing.assert_close(prefix, out[:, :3])
        out.nan_to_num().square().sum().backward()
        self.assertTrue(all(p.grad is None or torch.isfinite(p.grad).all() for p in self.model.parameters()))

    def test_complexity_end_to_end(self):
        features = np.random.default_rng(8).normal(size=(40, 5, 9)).astype("float32")
        result = encode_scene(self.model, features, scene_id="hour_02")
        complexity = estimate_complexity(result.embeddings, scene_id=result.scene_id)
        self.assertEqual((complexity.n_samples, complexity.embedding_dim, complexity.scene_id), (40, 8, "hour_02"))
        json.dumps(complexity.to_dict(), allow_nan=False)
        with temporary_directory() as directory:
            points = Path(directory) / "hour.npy"
            np.save(points, result.embeddings)
            run = subprocess.run([sys.executable, "-m", "complexity", str(points)], cwd=ROOT,
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)["results"][0]["embedding_dim"], 8)


class CheckpointTests(unittest.TestCase):
    def test_round_trip_with_metadata_pooling_and_exact_predictions(self):
        model = build_model(SMALL)
        x = np.ones((2, 4, 9), dtype=np.float32)
        config = EmbeddingConfig(pooling="gem", gem_p=2)
        with temporary_directory() as directory:
            path = Path(directory) / "model.pt"
            save_model(model, path, embedding_config=config, metadata={"seed": 0, "data_version": "fixture"})
            loaded = load_model(path)
            self.assertFalse(loaded.training)
            self.assertEqual(loaded.checkpoint_metadata["data_version"], "fixture")
            self.assertEqual(loaded.embedding_config, config)
            np.testing.assert_array_equal(encode_scene(model, x, config=config).embeddings,
                                          encode_scene(loaded, x).embeddings)
            with self.assertRaisesRegex(ValueError, "conflicts"):
                load_model(path, config=replace(SMALL, output_dims=16))

    def test_legacy_wrappers_require_original_config(self):
        model = build_model(SMALL)
        with temporary_directory() as directory:
            path = Path(directory) / "legacy.pt"
            for wrapper in (None, "state_dict", "model_state_dict", "model"):
                state = model.state_dict()
                torch.save({wrapper: state} if wrapper else state, path)
                with self.assertRaisesRegex(ValueError, "ORIGINAL"):
                    load_model(path)
                loaded = load_model(path, config=SMALL)
                torch.testing.assert_close(loaded.pre_proj.weight, model.pre_proj.weight)
                with self.assertRaisesRegex(ValueError, "does not match"):
                    load_model(path, config=replace(SMALL, output_dims=16))

    def test_rejects_missing_keys_bad_version_and_nonfinite(self):
        with temporary_directory() as directory:
            path = Path(directory) / "bad.pt"
            state = build_model(SMALL).state_dict()
            state.pop("pre_proj.bias")
            torch.save(state, path)
            with self.assertRaises(ValueError):
                load_model(path, config=SMALL)
            torch.save({"schema_version": 2}, path)
            with self.assertRaisesRegex(ValueError, "schema_version"):
                load_model(path)
            state = build_model(SMALL).state_dict()
            state["pre_proj.bias"][0] = float("nan")
            torch.save(state, path)
            with self.assertRaisesRegex(ValueError, "nonfinite"):
                load_model(path, config=SMALL)


class TrainingTests(unittest.TestCase):
    def test_one_step_train_validate_reload_and_budget(self):
        x = torch.randn(4, 6, 9)
        x[1, 4:] = float("nan")
        labels = torch.tensor([[0., 0., 1., 1., 2., 2.]]).repeat(4, 1)
        labels[1, 4:] = float("nan")
        loader = DataLoader(TensorDataset(x, labels), batch_size=2)
        config = TrainingConfig(epochs=3, max_steps=1, downsample=1)
        with temporary_directory() as directory:
            history = fit_encoder(build_model(SMALL), loader, output_dir=directory,
                                  validation_loader=loader, config=config, metadata={"data_version": "fixture"})
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["steps"], 1)
            self.assertTrue(np.isfinite(history[0]["validation_loss"]))
            for name in ("last.pt", "best.pt", "history.json"):
                self.assertTrue((Path(directory) / name).exists())
            loaded = load_model(Path(directory) / "best.pt")
            self.assertEqual(loaded.checkpoint_metadata["training_config"], config.to_dict())
            self.assertEqual(encode_scene(loaded, x.numpy()).embeddings.shape, (4, 8))

    def test_no_validation_and_empty_loader(self):
        x = torch.randn(2, 4, 9)
        y = torch.tensor([[0., 0., 1., 1.]]).repeat(2, 1)
        loader = DataLoader(TensorDataset(x, y), batch_size=2)
        with temporary_directory() as directory:
            fit_encoder(build_model(SMALL), loader, output_dir=directory, config=TrainingConfig(epochs=1))
            self.assertFalse((Path(directory) / "best.pt").exists())
        with temporary_directory() as directory, self.assertRaisesRegex(ValueError, "empty"):
            fit_encoder(build_model(SMALL), [], output_dir=directory, config=TrainingConfig(epochs=1))

    def test_feature_recipe_and_input_validation(self):
        positions = np.array([[[0., 0., 0.], [3., 4., 0.], [6., 8., 0.], [np.nan]*3]])
        dataset = make_dataset(positions, config=TrainingConfig(downsample=1))
        self.assertEqual(dataset.features.shape, (1, 3, 9))
        np.testing.assert_allclose(dataset.features[0, :, 3:6], [[0.6, 0.8, 0.]] * 3, atol=1e-6)
        np.testing.assert_allclose(dataset.features[0, :, 6], [0., 5., 10.])
        np.testing.assert_array_equal(positions[0, -1], [np.nan]*3)
        for bad in (np.ones((1, 1, 3)), np.full((1, 3, 3), np.inf), np.ones((1, 3, 9))):
            with self.assertRaises(ValueError):
                make_dataset(bad, config=TrainingConfig(downsample=1))

    def test_cli_help_and_offline_import(self):
        run = subprocess.run([sys.executable, "-m", "ATSCC.train", "--help"], cwd=ROOT,
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("--config", run.stdout)
        self.assertNotIn("wandb", sys.modules)

    def test_legacy_import_pooling_and_loader_restoration(self):
        script = '''
import numpy as np
import torch
from torch.utils.data import DataLoader
from atscc import apply_pooling, encode, load_model
from train import make_dataset
from config import TrainingConfig
from inference import build_model
from model.GPT import TSGPTEncoder
from datautils import pad_stack_train
x=np.random.default_rng(0).normal(size=(2, 6, 3)).astype('float32')
ds=make_dataset(x, config=TrainingConfig(downsample=1))
loader=DataLoader(ds, batch_size=2, collate_fn=pad_stack_train)
m=TSGPTEncoder(9,8,16,4,1,32,0.0)
a=encode(m, loader, 'cpu')
assert len(a)==5 and a[0].shape==(2,8) and not ds.eval
assert loader.collate_fn is pad_stack_train and m.training
try:
    encode(m, loader, 'cpu', pooling='bad')
except ValueError:
    pass
else:
    raise AssertionError('invalid pooling accepted')
assert not ds.eval and loader.collate_fn is pad_stack_train and m.training
assert torch.equal(apply_pooling(torch.ones(1,2,3),torch.zeros(1,2)),torch.full((1,3),2.))
'''
        run = subprocess.run([sys.executable, "-c", script], cwd=ROOT / "ATSCC", capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)


class IntegrationTests(unittest.TestCase):
    def test_dimension_controls_and_legacy_output_roundtrip(self):
        features = np.ones((2, 3, 9), dtype=np.float32)
        with temporary_directory() as directory:
            for dimension in (4, 8, 16, 320):
                with self.subTest(dimension=dimension):
                    config = replace(SMALL, output_dims=dimension)
                    model = build_model(config)
                    path = Path(directory) / f'model_{dimension}.pt'
                    save_model(model, path, metadata={'dimension': dimension})
                    loaded = load_model(path)
                    self.assertEqual(encode_scene(loaded, features).embeddings.shape, (2, dimension))
                    resaved = Path(directory) / f'resaved_{dimension}.pt'
                    save_model(loaded, resaved)
                    self.assertEqual(load_model(resaved).checkpoint_metadata, {'dimension': dimension})

    def test_training_cli_synthetic_end_to_end_and_no_overwrite(self):
        with temporary_directory() as directory:
            directory = Path(directory)
            positions = np.random.default_rng(3).normal(size=(2, 6, 3)).astype('float32')
            np.save(directory / 'train.npy', positions)
            np.save(directory / 'validation.npy', positions + 0.1)
            settings = {
                'encoder': SMALL.to_dict(),
                'training': TrainingConfig(epochs=1, batch_size=2, downsample=1, max_steps=1).to_dict(),
                'embedding': EmbeddingConfig().to_dict(),
            }
            config_path = directory / 'config.json'
            config_path.write_text(json.dumps(settings))
            output = directory / 'run'
            command = [sys.executable, '-m', 'ATSCC.train',
                       '--train-data', str(directory / 'train.npy'),
                       '--validation-data', str(directory / 'validation.npy'),
                       '--config', str(config_path), '--output-dir', str(output),
                       '--data-version', 'synthetic_v1', '--split-id', 'fixture_only', '--device', 'cpu']
            run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            model = load_model(output / 'best.pt')
            self.assertEqual(model.checkpoint_metadata['data_version'], 'synthetic_v1')
            self.assertEqual(model.checkpoint_metadata['split_id'], 'fixture_only')
            training = TrainingConfig(**model.checkpoint_metadata['training_config'])
            features = make_dataset(positions, config=training).features
            encoded = encode_scene(model, features, scene_id='fixture_hour')
            result = estimate_complexity(encoded.embeddings, scene_id=encoded.scene_id)
            self.assertEqual(result.reason, 'insufficient_samples')
            before = (output / 'best.pt').read_bytes()
            rerun = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(rerun.returncode, 2)
            self.assertIn('already contains a run', rerun.stderr)
            self.assertEqual((output / 'best.pt').read_bytes(), before)

    def test_pooling_partial_nan_is_not_silently_discarded(self):
        with self.assertRaises(ValueError):
            pool_hidden(torch.tensor([[[1., float('nan')], [2., 3.]]]))


if __name__ == "__main__":
    unittest.main()
