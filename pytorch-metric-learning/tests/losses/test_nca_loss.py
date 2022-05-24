import unittest

import torch

from pytorch_metric_learning.losses import NCALoss

from .. import TEST_DEVICE, TEST_DTYPES
from ..zzz_testing_utils.testing_utils import angle_to_coord


class TestNCALoss(unittest.TestCase):
    def test_nca_loss(self):
        softmax_scale = 10
        loss_func = NCALoss(softmax_scale=softmax_scale)

        for dtype in TEST_DTYPES:
            embedding_angles = [0, 20, 40, 60, 80]
            embeddings = torch.tensor(
                [angle_to_coord(a) for a in embedding_angles],
                requires_grad=True,
                dtype=dtype,
            ).to(
                TEST_DEVICE
            )  # 2D embeddings
            labels = torch.LongTensor([0, 0, 1, 1, 2])

            loss = loss_func(embeddings, labels)
            loss.backward()

            pos_pairs = [(0, 1), (1, 0), (2, 3), (3, 2)]
            neg_pairs = [
                (0, 2),
                (0, 3),
                (0, 4),
                (1, 2),
                (1, 3),
                (1, 4),
                (2, 0),
                (2, 1),
                (2, 4),
                (3, 0),
                (3, 1),
                (3, 4),
                (4, 0),
                (4, 1),
                (4, 2),
                (4, 3),
            ]

            embeddings = torch.nn.functional.normalize(embeddings)
            correct_total = 0
            for a1, p in pos_pairs:
                anchor1, positive = embeddings[a1], embeddings[p]
                ap_dist = torch.sum((anchor1 - positive) ** 2)
                numerator = torch.exp(-ap_dist * softmax_scale)
                denominator = numerator.clone()
                for a2, n in neg_pairs:
                    if a2 == a1:
                        anchor2, negative = embeddings[a2], embeddings[n]
                        an_dist = torch.sum((anchor2 - negative) ** 2)
                        denominator += torch.exp(-an_dist * softmax_scale)

                correct_total += -torch.log(numerator / denominator)

            correct_total /= len(pos_pairs)
            rtol = 1e-2 if dtype == torch.float16 else 1e-5
            self.assertTrue(torch.isclose(loss, correct_total, rtol=rtol))

    def test_zero_loss(self):
        loss_func = NCALoss(10)
        for dtype in TEST_DTYPES:
            for embedding_angles, labels in [([0, 20], [0, 0]), ([0], [0])]:
                embeddings = torch.tensor(
                    [angle_to_coord(a) for a in embedding_angles],
                    requires_grad=True,
                    dtype=dtype,
                ).to(
                    TEST_DEVICE
                )  # 2D embeddings
                labels = torch.LongTensor(labels)
                loss = loss_func(embeddings, labels)
                loss.backward()
                self.assertEqual(loss, 0)
