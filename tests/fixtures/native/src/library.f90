! SPDX-License-Identifier: MIT
module purifier_native_proof
 use iso_c_binding, only: c_int
 use jonquil, only: json_object, set_value, get_value
 implicit none
 contains
 function answer(delta) bind(C, name="purifier_answer") result(value)
  integer(c_int), value :: delta
  integer(c_int) :: value
  integer :: selected
  type(json_object) :: object
  call set_value(object, "answer", 42)
  call get_value(object, "answer", selected)
  value = int(selected, c_int) + delta
 end function answer
end module purifier_native_proof
