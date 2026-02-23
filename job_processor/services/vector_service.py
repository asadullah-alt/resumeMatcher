import torch
from typing import Dict, Any, List
from transformers import AutoModelForMaskedLM, AutoTokenizer
from job_processor.config import Config
from openai import OpenAI
from job_processor.logger import get_logger

logger = get_logger("job_processor.vector_service")

class VectorService:
    def __init__(self):
        logger.info(f"Loading SPLADE model: {Config.SPLADE_MODEL_ID}")
        self.tokenizer = AutoTokenizer.from_pretrained(Config.SPLADE_MODEL_ID)
        self.model = AutoModelForMaskedLM.from_pretrained(Config.SPLADE_MODEL_ID)
        logger.info("SPLADE model loaded successfully")

        # Initialize OpenAI Client for Dense
        logger.info(f"Initializing dense embedding client (model: {Config.DENSE_EMBEDDING_MODEL})")
        logger.info(f"[VectorService] OPENAI_BASE_URL={Config.OPENAI_BASE_URL!r}")
        api_key = Config.OPENAI_API_KEY or ""
        logger.info(f"[VectorService] OPENAI_API_KEY={'<empty>' if not api_key else api_key[:8] + '...' + api_key[-4:]}")
        self.openai_client = OpenAI(
            base_url=Config.OPENAI_BASE_URL,
            api_key=Config.OPENAI_API_KEY
        )

    def get_splade_vector(self, text: str, chunk_size: int = 448, overlap: int = 64) -> Dict[str, Any]:
        """
        Generates a sparse SPLADE vector using Chunking & Max-Pooling.
        """
        full_tokens = self.tokenizer(text, return_tensors="pt", add_special_tokens=False).input_ids[0]
        if len(full_tokens) == 0:
            logger.warning("SPLADE received empty token sequence — returning zero vector")
            return {"weight": 0.0, "tokens": {}}

        chunk_vectors = []
        step = chunk_size - overlap
        num_chunks = (len(full_tokens) + step - 1) // step
        logger.debug(f"SPLADE: processing {len(full_tokens)} tokens in {num_chunks} chunk(s)")

        for i in range(0, len(full_tokens), step):
            chunk_ids = full_tokens[i : i + chunk_size]
            input_ids = torch.cat([
                torch.tensor([self.tokenizer.cls_token_id]),
                chunk_ids,
                torch.tensor([self.tokenizer.sep_token_id])
            ]).unsqueeze(0)
            
            with torch.no_grad():
                logits = self.model(input_ids=input_ids).logits
                
            sparse_vec = torch.max(torch.log(1 + torch.relu(logits)), dim=1)[0].squeeze()
            chunk_vectors.append(sparse_vec)
        
        final_sparse_vec = torch.stack(chunk_vectors).max(dim=0)[0] if len(chunk_vectors) > 1 else chunk_vectors[0]
        
        cols = torch.nonzero(final_sparse_vec).squeeze()
        if cols.dim() == 0:
            cols = cols.unsqueeze(0)

        col_ids = cols.tolist()
        weights = final_sparse_vec[cols].tolist()
        tokens = self.tokenizer.convert_ids_to_tokens(col_ids)

        token_weights = {}
        sparse_indices = []
        sparse_values = []
        total_weight = 0.0
        for token, idx, weight in zip(tokens, col_ids, weights):
            if weight > 0.05:
                token_weights[token] = round(weight, 4)
                sparse_indices.append(idx)
                sparse_values.append(round(weight, 4))
                total_weight += weight

        logger.debug(f"SPLADE vector: {len(token_weights)} active tokens, total weight={round(total_weight, 4)}")
        return {
            "weight": round(total_weight, 4),
            "tokens": token_weights,
            "indices": sparse_indices,   # integer vocab IDs — ready for Qdrant SparseVector
            "values": sparse_values,     # corresponding float weights
        }

    def get_dense_vector(self, text: str, chunk_size: int = 4000) -> List[float]:
        """
        Generates a dense vector using OpenAI with chunking and max-pooling.
        """
        chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
        logger.debug(f"Dense embedding: processing {len(chunks)} chunk(s) of up to {chunk_size} chars each")
        
        weights = []
        for idx, chunk in enumerate(chunks):
            try:
                response = self.openai_client.embeddings.create(
                    input=chunk,
                    model=Config.DENSE_EMBEDDING_MODEL
                )
                weights.append(torch.tensor(response.data[0].embedding))
                logger.debug(f"Dense embedding chunk {idx + 1}/{len(chunks)} OK")
            except Exception as e:
                logger.error(f"Dense embedding failed on chunk {idx + 1}/{len(chunks)}: {e}", exc_info=True)
                raise
        
        if len(weights) == 1:
            final_vec = weights[0]
        else:
            final_vec = torch.stack(weights).max(dim=0)[0]

        logger.debug(f"Dense vector generated: dim={len(final_vec.tolist())}")
        return final_vec.tolist()
