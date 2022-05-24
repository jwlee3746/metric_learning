import unittest

import torch

from pytorch_metric_learning.losses import MarginLoss

from .. import TEST_DEVICE, TEST_DTYPES
from ..zzz_testing_utils.testing_utils import angle_to_coord
from .utils import get_triplet_embeddings_with_ref


class TestMarginLoss(unittest.TestCase):
    def helper(
        self, embeddings, labels, triplets, dtype, ref_emb=None, ref_labels=None
    ):
        for learn_beta, num_classes in [
            (False, None),
            (True, None),
            (False, 3),
            (True, 3),
        ]:
            margin, nu, beta = 0.1, 0.1, 1
            loss_func = MarginLoss(
                margin=margin,
                nu=nu,
                beta=beta,
                learn_beta=learn_beta,
                num_classes=num_classes,
            )

            loss = loss_func(embeddings, labels, ref_emb=ref_emb, ref_labels=ref_labels)

            correct_total_loss = 0
            num_non_zero = 0
            for a, p, n in triplets:
                anchor = embeddings[a]
                if ref_emb is not None:
                    positive, negative = ref_emb[p], ref_emb[n]
                else:
                    positive, negative = embeddings[p], embeddings[n]
                pos_loss = torch.relu(
                    torch.sqrt(torch.sum((anchor - positive) ** 2)) - beta + margin
                )
                neg_loss = torch.relu(
                    beta - torch.sqrt(torch.sum((anchor - negative) ** 2)) + margin
                )
                correct_total_loss += pos_loss + neg_loss
                if pos_loss > 0:
                    num_non_zero += 1
                if neg_loss > 0:
                    num_non_zero += 1

            if num_non_zero > 0:
                correct_total_loss /= num_non_zero
                if learn_beta:
                    if num_classes is None:
                        correct_beta_reg_loss = loss_func.beta * nu
                    else:
                        anchor_idx = [x[0] for x in triplets]
                        correct_beta_reg_loss = (
                            torch.sum(loss_func.beta[labels[anchor_idx]] * nu)
                            / num_non_zero
                        )
                    correct_total_loss += correct_beta_reg_loss.item()

            rtol = 1e-2 if dtype == torch.float16 else 1e-5
            self.assertTrue(torch.isclose(loss, correct_total_loss, rtol=rtol))

    def test_margin_loss(self):
        for dtype in TEST_DTYPES:
            embeddings = torch.randn(5, 32, requires_grad=True, dtype=dtype).to(
                TEST_DEVICE
            )
            embeddings = torch.nn.functional.normalize(embeddings)
            labels = torch.LongTensor([0, 0, 1, 1, 2])

            triplets = [
                (0, 1, 2),
                (0, 1, 3),
                (0, 1, 4),
                (1, 0, 2),
                (1, 0, 3),
                (1, 0, 4),
                (2, 3, 0),
                (2, 3, 1),
                (2, 3, 4),
                (3, 2, 0),
                (3, 2, 1),
                (3, 2, 4),
            ]

            self.helper(embeddings, labels, triplets, dtype)

    def test_margin_loss_with_ref(self):
        for dtype in TEST_DTYPES:
            (
                embeddings,
                labels,
                ref_emb,
                ref_labels,
                triplets,
            ) = get_triplet_embeddings_with_ref(dtype, TEST_DEVICE)
            self.helper(embeddings, labels, triplets, dtype, ref_emb, ref_labels)

    def test_with_no_valid_triplets(self):
        margin, nu, beta = 0.1, 0, 1
        loss_func = MarginLoss(margin=margin, nu=nu, beta=beta)
        for dtype in TEST_DTYPES:
            embedding_angles = [0, 20, 40, 60, 80]
            embeddings = torch.tensor(
                [angle_to_coord(a) for a in embedding_angles],
                requires_grad=True,
                dtype=dtype,
            ).to(
                TEST_DEVICE
            )  # 2D embeddings
            labels = torch.LongTensor([0, 1, 2, 3, 4])
            loss = loss_func(embeddings, labels)
            loss.backward()
            self.assertEqual(loss, 0)

    def test_beta_datatype(self):
        margin, nu, beta = 0.1, 0, 1
        loss_func = MarginLoss(margin=margin, nu=nu, beta=beta)
        self.assertTrue(len(loss_func.beta) == 1)
        loss_func = MarginLoss(margin=margin, nu=nu, beta=beta, learn_beta=True)
        self.assertTrue(len(loss_func.beta) == 1)
        loss_func = MarginLoss(
            margin=margin, nu=nu, beta=beta, learn_beta=True, num_classes=35
        )
        self.assertTrue(len(loss_func.beta) == 35)
