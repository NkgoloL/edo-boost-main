import random
from app.api.ml.irt_engine import (
    Item,
    Response,
    AssessmentSession,
    SubjectCode,
    p_correct,
    update_theta_mle,
    select_next_item,
    should_stop,
)

def simulate_learner(true_theta: float, item_bank: list[Item], max_q: int = 20):
    session = AssessmentSession(learner_grade=3, subject=SubjectCode.MATH)
    administered = set()
    items_dict = {i.item_id: i for i in item_bank}
    
    for _ in range(max_q):
        item = select_next_item(session, item_bank, administered)
        if not item:
            break
            
        # Probability of correct answer based on true ability
        p = p_correct(true_theta, item.discrimination_a, item.difficulty_b)
        is_correct = random.random() < p
        
        session.responses.append(Response(item.item_id, is_correct, 5000))
        administered.add(item.item_id)
        
        session.theta, session.sem = update_theta_mle(session.responses, items_dict)
        if should_stop(session, max_q):
            break
            
    return session.theta, session.sem, len(session.responses)

def test_irt_convergence():
    """
    Verify that the IRT engine correctly converges to the learner's true ability.
    """
    # Create a dense item bank for testing
    bank = []
    for i in range(100):
        bank.append(Item(
            f"item_{i}", SubjectCode.MATH, 3, "CONC",
            difficulty_b=(i - 50) / 10.0, # -5 to 5
            discrimination_a=1.5,
            question_text="Q", options=["A", "B"], correct_index=0
        ))
        
    # Test learners at different levels
    levels = [-2.0, -1.0, 0.0, 1.0, 2.0]
    results = []
    for true_theta in levels:
        estimates = []
        for _ in range(20): # 20 simulations per level
            est, sem, count = simulate_learner(true_theta, bank)
            estimates.append(est)
            
        avg_est = sum(estimates) / len(estimates)
        error = abs(avg_est - true_theta)
        results.append((true_theta, avg_est, error))
        
    for true_theta, avg_est, error in results:
        print(f"True Theta: {true_theta:5.1f} | Avg Estimate: {avg_est:6.3f} | Error: {error:6.3f}")
        assert error < 0.7, f"Inaccuracy for theta {true_theta}: error={error:.3f}"

if __name__ == "__main__":
    test_irt_convergence()
