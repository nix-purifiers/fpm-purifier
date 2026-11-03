program check_answer
 use purifier_proof, only: answer
 implicit none
 if (answer() /= 42) error stop "wrong answer"
 print *, answer()
end program check_answer
