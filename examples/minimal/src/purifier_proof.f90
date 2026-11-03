module purifier_proof
 use jonquil, only: json_object, set_value, get_value
 implicit none
 contains
 function answer() result(value)
  integer :: value
  type(json_object) :: object
  call set_value(object, "answer", 42)
  call get_value(object, "answer", value)
 end function answer
end module purifier_proof
