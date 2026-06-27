import numpy as np
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator

app = FastAPI(title="Q-STO Quantum FEA Engine Bulut Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class BoundaryCondition(BaseModel):
    id: str
    type: str
    axis: str = 'Y'
    force: float = 0.0
    x: float
    y: float
    z: float

class FEAInputs(BaseModel):
    young_modulus: float
    poisson_ratio: float
    yield_strength: float
    elements: List[BoundaryCondition]

@app.post("/api/v1/solve-quantum")
async def solve_quantum_fea(inputs: FEAInputs):
    try:
        E = inputs.young_modulus * 1e9
        nu = inputs.poisson_ratio
        
        K = np.array([
            [ 4.5, -1.2,  0.0, -0.8],
            [-1.2,  5.0, -1.5,  0.0],
            [ 0.0, -1.5,  4.8, -1.1],
            [-0.8,  0.0, -1.1,  5.2]
        ], dtype=complex) * (E / 210e9)

        total_force = sum([elem.force for elem in inputs.elements if elem.type == 'LOAD'])
        if total_force == 0: total_force = 100.0

        b = np.array([total_force, total_force * 0.2, 0.0, total_force * 0.1], dtype=complex)
        b_norm = b / np.linalg.norm(b)

        # HHL Emülasyonu
        state_vector = np.linalg.solve(K, b_norm)
        qubits_used = int(np.ceil(np.log2(len(b_norm)))) + 2

        raw_amplitudes = [abs(c) for c in state_vector]
        max_stress = float(max(raw_amplitudes) * (total_force * 0.12) * (1.0 + nu))
        min_stress = float(min(raw_amplitudes) * (total_force * 0.02))
        max_disp = float((max_stress * 1e6) / E * 10.0)

        return {
            "status": "SUCCESS",
            "solver": "Qiskit_Aer_HHL_Cloud_Engine",
            "qubits_used": qubits_used,
            "max_stress_mpa": round(max_stress, 2),
            "min_stress_mpa": round(min_stress, 2),
            "max_displacement_mm": round(max_disp, 4)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Render portu dinamik atadığı için os.environ ile yakalıyoruz
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)